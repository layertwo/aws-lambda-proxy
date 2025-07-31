"""Translate request from AWS api-gateway.

Freely adapted from https://github.com/aws/chalice

"""

import base64
import inspect
import json
import logging
import os
import re
import sys
import warnings
import zlib
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from aws_lambda_proxy import StatusCode
from aws_lambda_proxy.gateway import ApigwPath
from aws_lambda_proxy.patterns import (
    param_pattern,
    params_expr,
)
from aws_lambda_proxy.routing import RouteEntry, _converters
from aws_lambda_proxy.templates import redoc, swagger
from aws_lambda_proxy.types import Response

BINARY_TYPES = [
    "application/octet-stream",
    "application/x-protobuf",
    "application/x-tar",
    "application/zip",
    "image/png",
    "image/jpeg",
    "image/jpg",
    "image/tiff",
    "image/webp",
    "image/jp2",
]


class API:
    """API."""

    FORMAT_STRING = "[%(name)s] - [%(levelname)s] - %(message)s"

    def __init__(
        self,
        name: str,
        version: str = "0.0.1",
        description: Optional[str] = None,
        add_docs: bool = True,
        configure_logs: bool = True,
        debug: bool = False,
        https: bool = True,
    ) -> None:
        """Initialize API object."""
        self.name: str = name
        self.description: Optional[str] = description
        self.version: str = version
        self.routes: List[RouteEntry] = []
        self.context: Dict = {}
        self.event: Dict = {}
        self.request_path: ApigwPath
        self.debug: bool = debug
        self.https: bool = https
        self.log = logging.getLogger(self.name)
        if configure_logs:
            self._configure_logging()
        if add_docs:
            self.setup_docs()

    @property
    def host(self) -> str:
        """Construct api gateway endpoint url."""
        host = self.event["headers"].get(
            "x-forwarded-host", self.event["headers"].get("host", "")
        )
        path_info = self.request_path
        if path_info.apigw_stage and path_info.apigw_stage != "$default":
            host_suffix = f"/{path_info.apigw_stage}"
        else:
            host_suffix = path_info.path_mapping

        scheme = "https" if self.https else "http"
        return f"{scheme}://{host}{host_suffix}"

    def _get_parameters(self, route: RouteEntry) -> List[Dict]:
        argspath_schema = {
            "default": {"type": "string"},
            "string": {"type": "string"},
            "str": {"type": "string"},
            "regex": {"type": "string", "pattern": ""},
            "uuid": {"type": "string", "format": "uuid"},
            "int": {"type": "integer"},
            "float": {"type": "number", "format": "float"},
        }

        args_in_path = route._get_path_args()
        endpoint_args = inspect.signature(route.endpoint).parameters
        endpoint_args_names = list(endpoint_args.keys())

        parameters: List[Dict] = []
        for arg in args_in_path:
            annotation = endpoint_args[arg["name"]]
            endpoint_args_names.remove(arg["name"])

            parameter = {
                "name": arg["name"],
                "in": "path",
                "schema": {"type": "string"},
            }

            if arg["type"] is not None:
                parameter["schema"] = argspath_schema[arg["type"]]
                if arg["type"] == "regex":
                    parameter["schema"]["pattern"] = f"^{arg['pattern']}$"

            if annotation.default is not inspect.Parameter.empty:
                parameter["schema"]["default"] = annotation.default
            else:
                parameter["required"] = True

            parameters.append(parameter)

        for name, arg in endpoint_args.items():
            if name not in endpoint_args_names:
                continue
            parameter = {"name": name, "in": "query", "schema": {}}
            if arg.default is not inspect.Parameter.empty:
                parameter["schema"]["default"] = arg.default
            elif arg.kind == inspect.Parameter.VAR_KEYWORD:
                parameter["schema"]["format"] = "dict"
            else:
                parameter["schema"]["format"] = "string"
                parameter["required"] = True

            parameters.append(parameter)
        return parameters

    def _get_openapi(
        self, openapi_version: str = "3.0.2", openapi_prefix: str = ""
    ) -> Dict:
        """Get OpenAPI documentation."""
        info = {"title": self.name, "version": self.version}
        if self.description:
            info["description"] = self.description
        output = {"openapi": openapi_version, "info": info}

        security_schemes = {
            "access_token": {
                "type": "apiKey",
                "description": "Simple token authentification",
                "in": "query",
                "name": "access_token",
            }
        }

        components: Dict[str, Dict] = {}
        paths: Dict[str, Dict] = {}

        for route in self.routes:
            path: Dict[str, Dict] = {}

            default_operation: Dict[str, Any] = {}
            if route.tag:
                default_operation["tags"] = route.tag
            if route.description:
                default_operation["description"] = route.description
            if route.token:
                components.setdefault("securitySchemes", {}).update(security_schemes)
                default_operation["security"] = [{"access_token": []}]

            parameters = self._get_parameters(route)
            if parameters:
                default_operation["parameters"] = parameters

            default_operation["responses"] = {
                400: {"description": "Not found"},
                500: {"description": "Internal error"},
            }

            for method in route.methods:
                operation = default_operation.copy()
                operation["operationId"] = route.openapi_path
                if method in ["PUT", "POST", "DELETE", "PATCH"]:
                    operation["requestBody"] = {
                        "description": "Body",
                        "content": {"*/*": {}},
                        "required": operation["parameters"][0].get("required", "False"),
                    }
                    operation["parameters"] = operation["parameters"][1:]

                path[method.lower()] = operation

            paths.setdefault(openapi_prefix + route.openapi_path, {}).update(path)

        if components:
            output["components"] = components

        output["paths"] = paths
        return output

    def _configure_logging(self) -> None:
        if self._already_configured(self.log):
            return

        handler = logging.StreamHandler(sys.stdout)
        # Timestamp is handled by lambda itself so the
        # default FORMAT_STRING doesn't need to include it.
        formatter = logging.Formatter(self.FORMAT_STRING)
        handler.setFormatter(formatter)
        self.log.propagate = False
        if self.debug:
            level = logging.DEBUG
        else:
            level = logging.ERROR
        self.log.setLevel(level)
        self.log.addHandler(handler)

    def _already_configured(self, log) -> bool:
        if not log.handlers:
            return False

        for handler in log.handlers:
            if isinstance(handler, logging.StreamHandler):
                if handler.stream == sys.stdout:
                    return True

        return False

    def _add_route(self, path: str, endpoint: Callable, **kwargs) -> RouteEntry:
        methods = kwargs.pop("methods", ["GET"])
        cors = kwargs.pop("cors", False)
        token = kwargs.pop("token", "")
        payload_compression = kwargs.pop("payload_compression_method", "")
        binary_encode = kwargs.pop("binary_b64encode", False)
        ttl = kwargs.pop("ttl", None)
        cache_control = kwargs.pop("cache_control", None)
        description = kwargs.pop("description", None)
        tag = kwargs.pop("tag", None)

        if ttl:
            warnings.warn(
                "ttl will be deprecated in 6.0.0, please use 'cache-control'",
                DeprecationWarning,
                stacklevel=2,
            )

        if kwargs:
            raise TypeError(
                f"TypeError: route() got unexpected keyword "
                f"arguments: {', '.join(list(kwargs))}"
            )

        for method in methods:
            if self._checkroute(path, method):
                raise ValueError(
                    f'Duplicate route detected: "{path}"\n' "URL paths must be unique."
                )

        route = RouteEntry(
            endpoint,
            path,
            methods,
            cors,
            token,
            payload_compression,
            binary_encode,
            ttl,
            cache_control,
            description,
            tag,
        )
        self.routes.append(route)
        return route

    def _checkroute(self, path: str, method: str) -> bool:
        for route in self.routes:
            if method in route.methods and path == route.path:
                return True
        return False

    def _url_matching(self, url: str, method: str) -> Optional[RouteEntry]:
        for route in self.routes:
            expr = re.compile(route.route_regex)
            if method in route.methods and expr.match(url):
                return route

        return None

    def _get_matching_args(self, route: RouteEntry, url: str) -> Dict:
        route_expr = re.compile(route.route_regex)
        route_args = [i.group() for i in params_expr.finditer(route.path)]
        url_args = route_expr.match(url).groups()

        names = [param_pattern.match(arg).groupdict()["name"] for arg in route_args]

        args = [
            _converters(u, route_args[id])
            for id, u in enumerate(url_args)
            if u != route_args[id]
        ]

        return dict(zip(names, args))

    def _validate_token(self, token: Optional[str] = None) -> bool:
        env_token = os.environ.get("TOKEN")

        if not token or not env_token:
            return False

        if token == env_token:
            return True

        return False

    def route(self, path: str, **kwargs) -> Callable:
        """Register route."""

        def _register_view(endpoint):
            self._add_route(path, endpoint, **kwargs)
            return endpoint

        return _register_view

    def get(self, path: str, **kwargs) -> Callable:
        """Register GET route."""
        kwargs["methods"] = ["GET"]
        return self.route(path, **kwargs)

    def post(self, path: str, **kwargs) -> Callable:
        """Register POST route."""
        kwargs["methods"] = ["POST"]
        return self.route(path, **kwargs)

    def put(self, path: str, **kwargs) -> Callable:
        """Register PUT route."""
        kwargs["methods"] = ["PUT"]
        return self.route(path, **kwargs)

    def patch(self, path: str, **kwargs) -> Callable:
        """Register PATCH route."""
        kwargs["methods"] = ["PATCH"]
        return self.route(path, **kwargs)

    def delete(self, path: str, **kwargs) -> Callable:
        """Register DELETE route."""
        kwargs["methods"] = ["DELETE"]
        return self.route(path, **kwargs)

    def options(self, path: str, **kwargs) -> Callable:
        """Register OPTIONS route."""
        kwargs["methods"] = ["OPTIONS"]
        return self.route(path, **kwargs)

    def head(self, path: str, **kwargs) -> Callable:
        """Register HEAD route."""
        kwargs["methods"] = ["HEAD"]
        return self.route(path, **kwargs)

    def pass_context(self, f: Callable) -> Callable:
        """Decorator: pass the API Gateway context to the function."""

        @wraps(f)
        def new_func(*args, **kwargs) -> Callable:
            return f(self.context, *args, **kwargs)

        return new_func

    def pass_event(self, f: Callable) -> Callable:
        """Decorator: pass the API Gateway event to the function."""

        @wraps(f)
        def new_func(*args, **kwargs) -> Callable:
            return f(self.event, *args, **kwargs)

        return new_func

    def setup_docs(self) -> None:
        """Add default documentation routes."""
        openapi_url = "/openapi.json"

        def _openapi() -> Response:
            """Return OpenAPI json."""
            return Response(
                status_code=StatusCode.OK,
                content_type="application/json",
                body=json.dumps(
                    self._get_openapi(openapi_prefix=self.request_path.prefix)
                ),
            )

        self._add_route(openapi_url, _openapi, cors=True, tag=["documentation"])

        def _swagger_ui_html() -> Response:
            """Display Swagger HTML UI."""
            openapi_prefix = self.request_path.prefix
            return Response(
                status_code=StatusCode.OK,
                content_type="text/html",
                body=swagger(
                    openapi_url=f"{openapi_prefix}{openapi_url}",
                    title=self.name + " - Swagger UI",
                ),
            )

        self._add_route("/docs", _swagger_ui_html, cors=True, tag=["documentation"])

        def _redoc_ui_html() -> Response:
            """Display Redoc HTML UI."""
            openapi_prefix = self.request_path.prefix
            return Response(
                status_code=StatusCode.OK,
                content_type="text/html",
                body=redoc(
                    openapi_url=f"{openapi_prefix}{openapi_url}",
                    title=self.name + " - ReDoc",
                ),
            )

        self._add_route("/redoc", _redoc_ui_html, cors=True, tag=["documentation"])

    def response(
        self,
        response: Response,
        cors: bool = False,
        accepted_methods: Optional[Sequence[str]] = None,
        accepted_compression: str = "",
        compression: str = "",
        b64encode: bool = False,
        ttl: Optional[int] = None,
        cache_control: Optional[str] = None,
    ):
        """Return HTTP response.

        including response code (status), headers and body

        """
        accepted_methods = accepted_methods or []
        headers = response.headers or {}
        headers["Content-Type"] = response.content_type

        if cors:
            headers["Access-Control-Allow-Origin"] = "*"
            headers["Access-Control-Allow-Methods"] = ",".join(accepted_methods)
            headers["Access-Control-Allow-Credentials"] = "true"

        response_body = response.body
        if compression and compression in accepted_compression:
            headers["Content-Encoding"] = compression
            if isinstance(response_body, str):
                response_body = bytes(response_body, "utf-8")

            if compression == "gzip":
                gzip_compress = zlib.compressobj(9, zlib.DEFLATED, zlib.MAX_WBITS | 16)
                response_body = (
                    gzip_compress.compress(response_body) + gzip_compress.flush()
                )
            elif compression == "zlib":
                zlib_compress = zlib.compressobj(9, zlib.DEFLATED, zlib.MAX_WBITS)
                response_body = (
                    zlib_compress.compress(response_body) + zlib_compress.flush()
                )
            elif compression == "deflate":
                deflate_compress = zlib.compressobj(9, zlib.DEFLATED, -zlib.MAX_WBITS)
                response_body = (
                    deflate_compress.compress(response_body) + deflate_compress.flush()
                )
            else:
                return self.response(
                    Response(
                        status_code=StatusCode.INTERNAL_SERVER_ERROR,
                        content_type="application/json",
                        body=json.dumps(
                            {
                                "errorMessage": f"Unsupported compression mode: {compression}"
                            }
                        ),
                    )
                )

        if ttl:
            headers["Cache-Control"] = (
                f"max-age={ttl}"
                if response.status_code == StatusCode.OK
                else "no-cache"
            )
        elif cache_control:
            headers["Cache-Control"] = (
                cache_control if response.status_code == StatusCode.OK else "no-cache"
            )

        message_data: Dict[str, Any] = {
            "headers": headers,
            "statusCode": response.status_code.value,
        }
        if (
            response.content_type in BINARY_TYPES or not isinstance(response_body, str)
        ) and b64encode:
            message_data["isBase64Encoded"] = True
            message_data["body"] = base64.b64encode(response_body).decode()  # type: ignore
        else:
            message_data["body"] = response_body

        return message_data

    def __call__(self, event, context):
        """Initialize route and handlers."""
        self.log.debug(json.dumps(event, default=str))

        self.event = event
        self.context = context

        # HACK: For an unknown reason some keys can have lower or upper case.
        # To make sure the app works well we cast all the keys to lowercase.
        headers = self.event.get("headers", {}) or {}
        self.event["headers"] = dict(
            (key.lower(), value) for key, value in headers.items()
        )

        self.request_path = ApigwPath(self.event)
        if self.request_path.path is None:
            return self.response(
                Response(
                    status_code=StatusCode.BAD_REQUEST,
                    content_type="application/json",
                    body=json.dumps({"errorMessage": "Missing or invalid path"}),
                )
            )

        http_method = event["httpMethod"]
        route_entry = self._url_matching(self.request_path.path, http_method)
        if not route_entry:
            error_message = (
                f"No view function for: {http_method} - {self.request_path.path}"
            )
            return self.response(
                Response(
                    status_code=StatusCode.BAD_REQUEST,
                    content_type="application/json",
                    body=json.dumps({"errorMessage": error_message}),
                )
            )

        request_params = event.get("queryStringParameters", {}) or {}
        if route_entry.token:
            if not self._validate_token(request_params.get("access_token")):
                return self.response(
                    Response(
                        status_code=StatusCode.INTERNAL_SERVER_ERROR,
                        content_type="application/json",
                        body=json.dumps({"message": "Invalid access token"}),
                    )
                )

        # remove access_token from kwargs
        request_params.pop("access_token", False)

        function_kwargs = self._get_matching_args(route_entry, self.request_path.path)
        function_kwargs.update(request_params.copy())
        if http_method in ["POST", "PUT", "PATCH"] and event.get("body"):
            body = event["body"]
            if event.get("isBase64Encoded"):
                body = base64.b64decode(body).decode()
            function_kwargs.update({"body": body})

        try:
            response = route_entry.endpoint(**function_kwargs)
        except Exception as err:
            self.log.error(str(err))
            response = Response(
                status_code=StatusCode.INTERNAL_SERVER_ERROR,
                content_type="application/json",
                body=json.dumps({"errorMessage": str(err)}),
            )

        return self.response(
            response=response,
            cors=route_entry.cors,
            accepted_methods=route_entry.methods,
            accepted_compression=self.event["headers"].get("accept-encoding", ""),
            compression=route_entry.compression,
            b64encode=route_entry.b64encode,
            ttl=route_entry.ttl,
            cache_control=route_entry.cache_control,
        )
