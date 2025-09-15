"""Test gateway functionality."""

from aws_lambda_proxy.gateway import ApigwPath, _get_apigw_stage, _get_request_path


def test_api_gateway_path_variations():
    """Test various ApigwPath scenarios for complete coverage."""
    # Test with version field
    event = {"version": "2.0", "path": "/test", "headers": {}}
    path = ApigwPath(event)
    assert path.version == "2.0"

    # Test with no version
    event = {"path": "/test", "headers": {}}
    path = ApigwPath(event)
    assert path.version is None


def test_get_apigw_stage_no_execute_api():
    """Test _get_apigw_stage when host is not execute-api."""
    event = {
        "headers": {"host": "example.com"},
        "requestContext": {"stage": "production"},
    }
    stage = _get_apigw_stage(event)
    assert stage == ""


def test_get_apigw_stage_x_forwarded_host():
    """Test _get_apigw_stage with x-forwarded-host header."""
    event = {
        "headers": {"x-forwarded-host": "api.execute-api.us-east-1.amazonaws.com"},
        "requestContext": {"stage": "production"},
    }
    stage = _get_apigw_stage(event)
    assert stage == "production"


def test_get_request_path_no_proxy():
    """Test _get_request_path when no proxy pattern matches."""
    event = {"resource": "/static/path", "path": "/static/path"}
    path = _get_request_path(event)
    assert path == "/static/path"


def test_get_request_path_with_proxy():
    """Test _get_request_path with proxy pattern match."""
    event = {
        "resource": "{proxy+}",
        "pathParameters": {"proxy": "test/path"},
        "path": "/test/path",
    }
    path = _get_request_path(event)
    assert path == "/test/path"
