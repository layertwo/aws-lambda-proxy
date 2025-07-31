"""Route management and path conversion utilities."""

import re
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from aws_lambda_proxy.patterns import param_pattern, params_expr, regex_pattern


def _path_to_regex(path: str) -> str:
    path = f"^{path}$"  # full match
    path = re.sub(r"<[a-zA-Z0-9_]+>", r"([a-zA-Z0-9_]+)", path)
    path = re.sub(r"<string\:[a-zA-Z0-9_]+>", r"([a-zA-Z0-9_]+)", path)
    path = re.sub(r"<int\:[a-zA-Z0-9_]+>", r"([0-9]+)", path)
    path = re.sub(r"<float\:[a-zA-Z0-9_]+>", "([+-]?[0-9]+.[0-9]+)", path)
    path = re.sub(
        r"<uuid\:[a-zA-Z0-9_]+>",
        "([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})",
        path,
    )
    for param in re.findall(r"(<regex[^>]*>)", path):
        matches = regex_pattern.search(param)
        expr = matches.groupdict()["pattern"]
        path = path.replace(param, f"({expr})")

    return path


def _path_to_openapi(path: str) -> str:
    for param in re.findall(r"(<regex[^>]*>)", path):
        match = regex_pattern.search(param).groupdict()
        name = match["name"]
        path = path.replace(param, f"<regex:{name}>")

    path = re.sub(r"<([a-zA-Z0-9_]+\:)?", "{", path)
    return re.sub(r">", "}", path)


def _converters(value: str, path_arg: str) -> Any:
    match = param_pattern.match(path_arg)
    if match:
        arg_type = match.groupdict()["type"]
        if arg_type == "int":
            return int(value)
        if arg_type == "float":
            return float(value)
        if arg_type in ["string", "uuid"]:
            return value
    return value


class RouteEntry:
    """Decode request path."""

    def __init__(
        self,
        endpoint: Callable,
        path: str,
        methods: Optional[List[str]] = None,
        cors: bool = False,
        token: bool = False,
        payload_compression_method: str = "",
        binary_b64encode: bool = False,
        ttl: Optional[int] = None,
        cache_control: Optional[str] = None,
        description: Optional[str] = None,
        tag: Optional[Tuple] = None,
    ) -> None:
        """Initialize route object."""
        self.endpoint = endpoint
        self.path = path
        self.route_regex = _path_to_regex(path)
        self.openapi_path = _path_to_openapi(self.path)
        self.methods = methods or ["GET"]
        self.cors = cors
        self.token = token
        self.compression = payload_compression_method
        self.b64encode = binary_b64encode
        self.ttl = ttl
        self.cache_control = cache_control
        self.description = description or self.endpoint.__doc__
        self.tag = tag
        if self.compression and self.compression not in [
            "gzip",
            "zlib",
            "deflate",
        ]:
            raise ValueError(
                f"'{payload_compression_method}' is not a supported compression"
            )

    def __eq__(self, other) -> bool:
        """Check for equality."""
        return self.__dict__ == other.__dict__

    def _get_path_args(self) -> Sequence[Any]:
        route_args = [i.group() for i in params_expr.finditer(self.path)]
        args = [param_pattern.match(arg).groupdict() for arg in route_args]
        return args
