"""API Gateway path parsing and management."""

from typing import Dict, Optional

from aws_lambda_proxy.patterns import proxy_pattern


def _get_apigw_stage(event: Dict) -> str:
    """Return API Gateway stage name."""
    header = event.get("headers", {})
    host = header.get("x-forwarded-host", header.get("host", ""))
    if ".execute-api." in host and ".amazonaws.com" in host:
        stage = event["requestContext"].get("stage", "")
        return stage
    return ""


def _get_request_path(event: Dict) -> Optional[str]:
    """Return API call path."""
    resource_proxy = proxy_pattern.search(event.get("resource", "/"))
    if resource_proxy:
        proxy_path = event["pathParameters"].get(resource_proxy["name"])
        return f"/{proxy_path}"

    return event.get("path")


class ApigwPath:
    """Parse path of API Call."""

    def __init__(self, event: Dict):
        """Initialize API Gateway Path Info object."""
        self.version = event.get("version")
        self.apigw_stage = _get_apigw_stage(event)
        self.path = _get_request_path(event)
        self.api_prefix = proxy_pattern.sub("", event.get("resource", "")).rstrip("/")
        if not self.apigw_stage and self.path:
            path = event.get("path", "")
            suffix = self.api_prefix + self.path
            self.path_mapping = path.replace(suffix, "")
        else:
            self.path_mapping = ""

    @property
    def prefix(self):
        """Return the API prefix."""
        if self.apigw_stage and self.apigw_stage != "$default":
            return f"/{self.apigw_stage}" + self.api_prefix
        if self.path_mapping:
            return self.path_mapping + self.api_prefix
        return self.api_prefix
