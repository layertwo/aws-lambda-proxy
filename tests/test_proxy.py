"""Test aws-lambda-proxy."""

import base64
import json
import zlib
from typing import Dict
from unittest.mock import Mock

import pytest

from aws_lambda_proxy import StatusCode
from aws_lambda_proxy.proxy import API
from aws_lambda_proxy.routing import (
    RouteEntry,
    _converters,
    _path_to_openapi,
    _path_to_regex,
)
from aws_lambda_proxy.types import Response


def test_value_converters():
    """Convert convert value to correct type."""
    path_arg = "<string:v>"
    assert "123" == _converters("123", path_arg)

    path_arg = "<int:v>"
    assert 123 == _converters("123", path_arg)

    path_arg = "<float:v>"
    assert 123.0 == _converters("123", path_arg)

    path_arg = "<uuid:v>"
    assert "f5c21e12-8317-11e9-bf96-2e2ca3acb545" == _converters(
        "f5c21e12-8317-11e9-bf96-2e2ca3acb545", path_arg
    )

    path_arg = "<v>"
    assert "123" == _converters("123", path_arg)


def test_path_to_regex_convert():
    """Convert route path to regex."""
    path = "/jqtrde/<a>/<string:path>/<int:num>/<float:fl>/<uuid:id>/<regex([A-Z0-9]{5}):var>/<regex([a-z]{1}):othervar>"
    assert (
        "^/jqtrde/([a-zA-Z0-9_]+)/([a-zA-Z0-9_]+)/([0-9]+)/([+-]?[0-9]+.[0-9]+)/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})/([A-Z0-9]{5})/([a-z]{1})$"
        == _path_to_regex(path)
    )


def test_path_to_openapi_converters():
    """Convert proxy path to openapi path."""
    path = "/<string:num>/<test>-<regex([0-1]{4}):var>"
    assert "/{num}/{test}-{var}" == _path_to_openapi(path)


def test_RouteEntry_default(funct):
    """Should work as expected."""
    route = RouteEntry(funct, "/endpoint/test/<id>")
    assert route.endpoint == funct
    assert route.methods == ["GET"]
    assert not route.cors
    assert not route.token
    assert not route.compression
    assert not route.b64encode


def test_RouteEntry_Options(funct):
    """Should work as expected."""
    route = RouteEntry(
        funct,
        "/endpoint/test/<id>",
        ["POST"],
        cors=True,
        token="Yo",
        payload_compression_method="deflate",
        binary_b64encode=True,
    )
    assert route.endpoint == funct
    assert route.methods == ["POST"]
    assert route.cors
    assert route.token == "Yo"
    assert route.compression == "deflate"
    assert route.b64encode


def test_RouteEntry_invalidCompression(funct):
    """Should work as expected."""
    with pytest.raises(ValueError):
        RouteEntry(
            funct,
            "/endpoint/test/<id>",
            payload_compression_method="nope",
        )


def test_API_init():
    """Should work as expected."""
    app = API(name="test")
    assert app.name == "test"
    assert len(list(app.routes)) == 3
    assert not app.debug
    assert app.log.getEffectiveLevel() == 40  # ERROR

    # Clear logger handlers
    for h in app.log.handlers:
        app.log.removeHandler(h)


# Additional coverage tests for proxy module


def test_already_configured_no_handlers():
    """Test _already_configured method when logger has no handlers."""
    import logging

    app = API(name="test", configure_logs=False)
    # Create a logger with no handlers
    empty_logger = logging.getLogger("empty_test")
    empty_logger.handlers = []

    # This should return False when no handlers exist
    result = app._already_configured(empty_logger)
    assert result is False


def test_already_configured_with_different_stream():
    """Test _already_configured method when handler has different stream."""
    import logging
    import sys

    app = API(name="test", configure_logs=False)

    # Create a logger with a handler that doesn't use stdout
    test_logger = logging.getLogger("stream_test")
    test_logger.handlers = []

    # Add a handler with a different stream
    handler = logging.StreamHandler(sys.stderr)  # Not stdout
    test_logger.addHandler(handler)

    result = app._already_configured(test_logger)
    assert result is False

    # Clean up
    test_logger.removeHandler(handler)


def test_get_parameters_required_query_param():
    """Test _get_parameters with a required query parameter (no default)."""

    app = API(name="test")

    def endpoint_with_required_param(path_param: str, required_query: str):
        """Test endpoint with required query parameter."""
        return Response(StatusCode.OK, "text/plain", "test")

    route = RouteEntry(endpoint_with_required_param, "/<path_param>")
    parameters = app._get_parameters(route)

    # Should have both path parameter and required query parameter
    assert len(parameters) == 2

    # Find the query parameter
    query_param = next(p for p in parameters if p["in"] == "query")
    assert query_param["name"] == "required_query"
    assert query_param["required"] is True
    assert query_param["schema"]["format"] == "string"


def test_get_parameters_var_keyword():
    """Test _get_parameters with **kwargs parameter."""
    app = API(name="test")

    def endpoint_with_kwargs(path_param: str, **kwargs):
        """Test endpoint with **kwargs."""
        return Response(StatusCode.OK, "text/plain", "test")

    route = RouteEntry(endpoint_with_kwargs, "/<path_param>")
    parameters = app._get_parameters(route)

    # Should have path parameter and kwargs parameter
    assert len(parameters) == 2

    # Find the kwargs parameter
    kwargs_param = next(p for p in parameters if p["name"] == "kwargs")
    assert kwargs_param["in"] == "query"
    assert kwargs_param["schema"]["format"] == "dict"


def test_get_openapi_with_description():
    """Test _get_openapi when API has description."""
    app = API(name="test", description="Test API description")

    @app.get("/test")
    def test_endpoint():
        """Test endpoint."""
        return Response(StatusCode.OK, "text/plain", "test")

    openapi_doc = app._get_openapi()

    assert "description" in openapi_doc["info"]
    assert openapi_doc["info"]["description"] == "Test API description"


def test_add_route_token_boolean():
    """Test _add_route with token as boolean (line 145 coverage)."""
    app = API(name="test")

    def test_endpoint():
        return Response(StatusCode.OK, "text/plain", "test")

    # Test with token=True (boolean, not string)
    route = app._add_route("/test", test_endpoint, token=True)
    assert route.token is True


def test_get_parameters_regex_type():
    """Test _get_parameters with regex parameter type (line coverage)."""
    app = API(name="test")

    def endpoint_with_regex_param(user_id):
        """Test endpoint with regex parameter."""
        return Response(StatusCode.OK, "text/plain", f"User {user_id}")

    # Create route with regex parameter
    route = RouteEntry(endpoint_with_regex_param, "/user/<regex([0-9]+):user_id>")
    parameters = app._get_parameters(route)

    # Should have the regex parameter with pattern
    assert len(parameters) == 1
    param = parameters[0]
    assert param["name"] == "user_id"
    assert param["schema"]["type"] == "string"
    assert "pattern" in param["schema"]
    assert param["schema"]["pattern"] == "^[0-9]+$"


def test_get_openapi_with_components():
    """Test _get_openapi when components are added (line 115)."""
    app = API(name="test")

    @app.get("/secure", token=True)
    def secure_endpoint():
        """Secure endpoint requiring token."""
        return Response(StatusCode.OK, "text/plain", "secure")

    openapi_doc = app._get_openapi()

    # Should have components section with security schemes
    assert "components" in openapi_doc
    assert "securitySchemes" in openapi_doc["components"]
    assert "access_token" in openapi_doc["components"]["securitySchemes"]


def test_get_parameters_path_with_default():
    """Test _get_parameters with path parameter that has default value."""
    app = API(name="test")

    def endpoint_with_default(path_param: str = "default_value"):
        """Test endpoint with default parameter."""
        return Response(StatusCode.OK, "text/plain", "test")

    route = RouteEntry(endpoint_with_default, "/<path_param>")
    parameters = app._get_parameters(route)

    # Should have parameter with default value
    assert len(parameters) == 1
    param = parameters[0]
    assert param["name"] == "path_param"
    assert "default" in param["schema"]
    assert param["schema"]["default"] == "default_value"
    assert "required" not in param  # Should not be required since it has default


def test_host_property_with_path_mapping():
    """Test host property when apigw_stage is None or $default (lines 74-84)."""

    app = API(name="test")

    # Mock event and request_path to trigger the else branch
    app.event = {"headers": {"host": "api.example.com"}}

    # Create a mock ApigwPath with path_mapping
    mock_path = Mock()
    mock_path.apigw_stage = None  # This should trigger the else branch
    mock_path.path_mapping = "/stage"
    app.request_path = mock_path

    host = app.host
    assert host == "https://api.example.com/stage"

    # Test with $default stage
    mock_path.apigw_stage = "$default"
    host = app.host
    assert host == "https://api.example.com/stage"


def test_host_property_with_x_forwarded_host():
    """Test host property with x-forwarded-host header."""
    app = API(name="test")

    # Test with x-forwarded-host (should take precedence over host)
    app.event = {
        "headers": {
            "x-forwarded-host": "forwarded.example.com",
            "host": "original.example.com",
        }
    }

    mock_path = Mock()
    mock_path.apigw_stage = "prod"
    mock_path.path_mapping = "/mapping"
    app.request_path = mock_path

    host = app.host
    assert host == "https://forwarded.example.com/prod"


def test_host_property_http_scheme():
    """Test host property with HTTP scheme instead of HTTPS."""
    app = API(name="test", https=False)  # Set HTTPS to False

    app.event = {"headers": {"host": "api.example.com"}}

    mock_path = Mock()
    mock_path.apigw_stage = "dev"
    mock_path.path_mapping = "/mapping"
    app.request_path = mock_path

    host = app.host
    assert host == "http://api.example.com/dev"  # Should use HTTP


def test_API_noDocs():
    """Do not set default documentation routes."""
    app = API(name="test", add_docs=False)
    assert app.name == "test"
    assert len(list(app.routes)) == 0
    assert not app.debug
    assert app.log.getEffectiveLevel() == 40  # ERROR

    # Clear logger handlers
    for h in app.log.handlers:
        app.log.removeHandler(h)


def test_API_noLog():
    """Should work as expected."""
    app = API(name="test", configure_logs=False)
    assert app.name == "test"
    assert not app.debug
    assert app.log

    # Clear logger handlers
    for h in app.log.handlers:
        app.log.removeHandler(h)


def test_API_logDebug():
    """Should work as expected."""
    app = API(name="test", debug=True)
    assert app.log.getEffectiveLevel() == 10  # DEBUG

    # Clear logger handlers
    for h in app.log.handlers:
        app.log.removeHandler(h)


def test_API_addRoute(funct):
    """Add and parse route."""
    app = API(name="test")
    assert len(list(app.routes)) == 3

    app._add_route("/endpoint/test/<id>", funct, methods=["GET"], cors=True, token="yo")
    assert app.routes

    with pytest.raises(ValueError):
        app._add_route("/endpoint/test/<id>", funct, methods=["GET"], cors=True)

    with pytest.raises(TypeError):
        app._add_route("/endpoint/test/<id>", funct, methods=["GET"], c=True)

    # Clear logger handlers
    for h in app.log.handlers:
        app.log.removeHandler(h)


def test_proxy_API():
    """Add and parse route."""
    app = API(name="test")
    funct = Mock(
        __name__="Mock", return_value=Response(StatusCode.OK, "text/plain", "heyyyy")
    )
    app._add_route("/test/<string:user>/<name>", funct, methods=["GET"], cors=True)

    event = {
        "path": "/test/remote/pixel",
        "httpMethod": "GET",
        "headers": {},
        "queryStringParameters": {},
    }
    resp = {
        "body": "heyyyy",
        "headers": {
            "Access-Control-Allow-Credentials": "true",
            "Access-Control-Allow-Methods": "GET",
            "Access-Control-Allow-Origin": "*",
            "Content-Type": "text/plain",
        },
        "statusCode": 200,
    }
    res = app(event, {})
    assert res == resp
    funct.assert_called_with(user="remote", name="pixel")


def test_proxy_APIpath():
    """Add and parse route."""
    app = API(name="test")
    funct = Mock(
        __name__="Mock", return_value=Response(StatusCode.OK, "text/plain", "heyyyy")
    )
    app._add_route("/test/<string:user>/<name>", funct, methods=["GET"], cors=True)

    event = {
        "resource": "/",
        "path": "/test/remote/pixel",
        "httpMethod": "GET",
        "headers": {},
        "queryStringParameters": {},
    }
    resp = {
        "body": "heyyyy",
        "headers": {
            "Access-Control-Allow-Credentials": "true",
            "Access-Control-Allow-Methods": "GET",
            "Access-Control-Allow-Origin": "*",
            "Content-Type": "text/plain",
        },
        "statusCode": 200,
    }
    res = app(event, {})
    assert res == resp
    funct.assert_called_with(user="remote", name="pixel")


def test_proxy_APIpathProxy():
    """Add and parse route."""
    app = API(name="test")
    funct = Mock(
        __name__="Mock", return_value=Response(StatusCode.OK, "text/plain", "heyyyy")
    )
    app._add_route("/test/<string:user>/<name>", funct, methods=["GET"], cors=True)

    event = {
        "resource": "{something+}",
        "pathParameters": {"something": "test/remote/pixel"},
        "path": "/test/remote/pixel",
        "httpMethod": "GET",
        "headers": {},
        "queryStringParameters": {},
    }
    resp = {
        "body": "heyyyy",
        "headers": {
            "Access-Control-Allow-Credentials": "true",
            "Access-Control-Allow-Methods": "GET",
            "Access-Control-Allow-Origin": "*",
            "Content-Type": "text/plain",
        },
        "statusCode": 200,
    }
    res = app(event, {})
    assert res == resp
    funct.assert_called_with(user="remote", name="pixel")


def test_proxy_APIpathCustomDomain():
    """Add and parse route."""
    app = API(name="test")
    funct = Mock(
        __name__="Mock", return_value=Response(StatusCode.OK, "text/plain", "heyyyy")
    )
    app._add_route("/test/<string:user>/<name>", funct, methods=["GET"], cors=True)

    event = {
        "resource": "/{something+}",
        "pathParameters": {"something": "test/remote/pixel"},
        "path": "/myapi/test/remote/pixel",
        "httpMethod": "GET",
        "headers": {},
        "queryStringParameters": {},
    }
    resp = {
        "body": "heyyyy",
        "headers": {
            "Access-Control-Allow-Credentials": "true",
            "Access-Control-Allow-Methods": "GET",
            "Access-Control-Allow-Origin": "*",
            "Content-Type": "text/plain",
        },
        "statusCode": 200,
    }
    res = app(event, {})
    assert res == resp
    funct.assert_called_with(user="remote", name="pixel")


def test_ttl():
    """Add and parse route."""
    app = API(name="test")
    funct = Mock(
        __name__="Mock", return_value=Response(StatusCode.OK, "text/plain", "heyyyy")
    )
    with pytest.warns(DeprecationWarning):
        app._add_route(
            "/test/<string:user>/<name>",
            funct,
            methods=["GET"],
            cors=True,
            ttl=3600,
        )
        funct_error = Mock(
            __name__="Mock",
            return_value=Response(StatusCode.BAD_REQUEST, "text/plain", "heyyyy"),
        )
        app._add_route("/yo", funct_error, methods=["GET"], cors=True, ttl=3600)

    event = {
        "path": "/test/remote/pixel",
        "httpMethod": "GET",
        "headers": {},
        "queryStringParameters": {},
    }
    resp = {
        "body": "heyyyy",
        "headers": {
            "Access-Control-Allow-Credentials": "true",
            "Access-Control-Allow-Methods": "GET",
            "Access-Control-Allow-Origin": "*",
            "Content-Type": "text/plain",
            "Cache-Control": "max-age=3600",
        },
        "statusCode": 200,
    }
    res = app(event, {})
    assert res == resp
    funct.assert_called_with(user="remote", name="pixel")

    event = {
        "path": "/yo",
        "httpMethod": "GET",
        "headers": {},
        "queryStringParameters": {},
    }
    res = app(event, {})
    assert res["headers"]["Cache-Control"] == "no-cache"


def test_cache_control():
    """Add and parse route."""
    app = API(name="test")
    funct = Mock(
        __name__="Mock", return_value=Response(StatusCode.OK, "text/plain", "heyyyy")
    )
    app._add_route(
        "/test/<string:user>/<name>",
        funct,
        methods=["GET"],
        cors=True,
        cache_control="public,max-age=3600",
    )
    funct_error = Mock(
        __name__="Mock",
        return_value=Response(StatusCode.BAD_REQUEST, "text/plain", "heyyyy"),
    )
    app._add_route(
        "/yo",
        funct_error,
        methods=["GET"],
        cors=True,
        cache_control="public,max-age=3600",
    )

    event = {
        "path": "/test/remote/pixel",
        "httpMethod": "GET",
        "headers": {},
        "queryStringParameters": {},
    }
    resp = {
        "body": "heyyyy",
        "headers": {
            "Access-Control-Allow-Credentials": "true",
            "Access-Control-Allow-Methods": "GET",
            "Access-Control-Allow-Origin": "*",
            "Content-Type": "text/plain",
            "Cache-Control": "public,max-age=3600",
        },
        "statusCode": 200,
    }
    res = app(event, {})
    assert res == resp
    funct.assert_called_with(user="remote", name="pixel")

    event = {
        "path": "/yo",
        "httpMethod": "GET",
        "headers": {},
        "queryStringParameters": {},
    }
    res = app(event, {})
    assert res["headers"]["Cache-Control"] == "no-cache"


def test_querystringNull():
    """Add and parse route."""
    app = API(name="test")
    funct = Mock(
        __name__="Mock", return_value=Response(StatusCode.OK, "text/plain", "heyyyy")
    )
    app._add_route("/test/<user>", funct, methods=["GET"], cors=True)

    event = {
        "path": "/test/remotepixel",
        "httpMethod": "GET",
        "headers": {},
        "queryStringParameters": None,
    }
    resp = {
        "body": "heyyyy",
        "headers": {
            "Access-Control-Allow-Credentials": "true",
            "Access-Control-Allow-Methods": "GET",
            "Access-Control-Allow-Origin": "*",
            "Content-Type": "text/plain",
        },
        "statusCode": 200,
    }
    res = app(event, {})
    assert res == resp
    funct.assert_called_with(user="remotepixel")


def test_headersNull():
    """Add and parse route."""
    app = API(name="test")
    funct = Mock(
        __name__="Mock", return_value=Response(StatusCode.OK, "text/plain", "heyyyy")
    )
    app._add_route("/test/<user>", funct, methods=["GET"], cors=True)

    event = {
        "path": "/test/remotepixel",
        "httpMethod": "GET",
        "headers": None,
        "queryStringParameters": {},
    }
    resp = {
        "body": "heyyyy",
        "headers": {
            "Access-Control-Allow-Credentials": "true",
            "Access-Control-Allow-Methods": "GET",
            "Access-Control-Allow-Origin": "*",
            "Content-Type": "text/plain",
        },
        "statusCode": 200,
    }
    res = app(event, {})
    assert res == resp
    funct.assert_called_with(user="remotepixel")


def test_API_custom_headers():
    """Add and parse route."""
    app = API(name="test")
    funct = Mock(
        __name__="Mock",
        return_value=Response(
            status_code=StatusCode.OK,
            content_type="text/plain",
            body="heyyyy",
            headers={"X-Custom-Header": "foobar"},
        ),
    )
    app._add_route("/test/<user>", funct, methods=["GET"], cors=True)

    event = {
        "path": "/test/remotepixel",
        "httpMethod": "GET",
        "headers": None,
        "queryStringParameters": {},
    }
    resp = {
        "body": "heyyyy",
        "headers": {
            "Access-Control-Allow-Credentials": "true",
            "Access-Control-Allow-Methods": "GET",
            "Access-Control-Allow-Origin": "*",
            "Content-Type": "text/plain",
            "X-Custom-Header": "foobar",
        },
        "statusCode": 200,
    }
    res = app(event, {})
    assert res == resp


def test_API_encoding():
    """Test b64 encoding."""
    app = API(name="test")

    body = b"thisisafakeencodedjpeg"
    b64body = base64.b64encode(body).decode()

    funct = Mock(
        __name__="Mock", return_value=Response(StatusCode.OK, "image/jpeg", body)
    )
    app._add_route("/test/<user>.jpg", funct, methods=["GET"], cors=True)

    event = {
        "path": "/test/remotepixel.jpg",
        "httpMethod": "GET",
        "headers": {},
        "queryStringParameters": {},
    }
    resp = {
        "body": body,
        "headers": {
            "Access-Control-Allow-Credentials": "true",
            "Access-Control-Allow-Methods": "GET",
            "Access-Control-Allow-Origin": "*",
            "Content-Type": "image/jpeg",
        },
        "statusCode": 200,
    }
    res = app(event, {})
    assert res == resp

    app._add_route(
        "/test_encode/<user>.jpg",
        funct,
        methods=["GET"],
        cors=True,
        binary_b64encode=True,
    )
    event = {
        "path": "/test_encode/remotepixel.jpg",
        "httpMethod": "GET",
        "headers": {},
        "queryStringParameters": {},
    }
    resp = {
        "body": b64body,
        "headers": {
            "Access-Control-Allow-Credentials": "true",
            "Access-Control-Allow-Methods": "GET",
            "Access-Control-Allow-Origin": "*",
            "Content-Type": "image/jpeg",
        },
        "isBase64Encoded": True,
        "statusCode": 200,
    }
    res = app(event, {})
    assert res == resp


def test_API_compression():
    """Test compression and base64."""
    body = b"thisisafakeencodedjpeg"
    gzip_compress = zlib.compressobj(9, zlib.DEFLATED, zlib.MAX_WBITS | 16)
    gzbody = gzip_compress.compress(body) + gzip_compress.flush()
    b64gzipbody = base64.b64encode(gzbody).decode()

    app = API(name="test")
    funct = Mock(
        __name__="Mock", return_value=Response(StatusCode.OK, "image/jpeg", body)
    )
    app._add_route(
        "/test_compress/<user>.jpg",
        funct,
        methods=["GET"],
        cors=True,
        payload_compression_method="gzip",
    )

    # Should compress because "Accept-Encoding" is in header
    event = {
        "path": "/test_compress/remotepixel.jpg",
        "httpMethod": "GET",
        "headers": {"Accept-Encoding": "gzip, deflate"},
        "queryStringParameters": {},
    }
    resp = {
        "body": gzbody,
        "headers": {
            "Access-Control-Allow-Credentials": "true",
            "Access-Control-Allow-Methods": "GET",
            "Access-Control-Allow-Origin": "*",
            "Content-Encoding": "gzip",
            "Content-Type": "image/jpeg",
        },
        "statusCode": 200,
    }
    res = app(event, {})
    assert res == resp

    # Should not compress because "Accept-Encoding" is missing in header
    event = {
        "path": "/test_compress/remotepixel.jpg",
        "httpMethod": "GET",
        "headers": {},
        "queryStringParameters": {},
    }
    resp = {
        "body": body,
        "headers": {
            "Access-Control-Allow-Credentials": "true",
            "Access-Control-Allow-Methods": "GET",
            "Access-Control-Allow-Origin": "*",
            "Content-Type": "image/jpeg",
        },
        "statusCode": 200,
    }
    res = app(event, {})
    assert res == resp

    # Should compress and encode to base64
    app._add_route(
        "/test_compress_b64/<user>.jpg",
        funct,
        methods=["GET"],
        cors=True,
        payload_compression_method="gzip",
        binary_b64encode=True,
    )
    event = {
        "path": "/test_compress_b64/remotepixel.jpg",
        "httpMethod": "GET",
        "headers": {"Accept-Encoding": "gzip, deflate"},
        "queryStringParameters": {},
    }
    resp = {
        "body": b64gzipbody,
        "headers": {
            "Access-Control-Allow-Credentials": "true",
            "Access-Control-Allow-Methods": "GET",
            "Access-Control-Allow-Origin": "*",
            "Content-Encoding": "gzip",
            "Content-Type": "image/jpeg",
        },
        "isBase64Encoded": True,
        "statusCode": 200,
    }
    res = app(event, {})
    assert res == resp

    funct = Mock(
        __name__="Mock",
        return_value=Response(
            StatusCode.OK, "application/json", json.dumps({"test": 0})
        ),
    )
    # Should compress and encode to base64
    app._add_route(
        "/test_compress_b64/<user>.json",
        funct,
        methods=["GET"],
        cors=True,
        payload_compression_method="gzip",
        binary_b64encode=True,
    )
    event = {
        "path": "/test_compress_b64/remotepixel.json",
        "httpMethod": "GET",
        "headers": {"Accept-Encoding": "gzip, deflate"},
        "queryStringParameters": {},
    }

    body = bytes(json.dumps({"test": 0}), "utf-8")
    gzip_compress = zlib.compressobj(9, zlib.DEFLATED, zlib.MAX_WBITS | 16)
    gzbody = gzip_compress.compress(body) + gzip_compress.flush()
    b64gzipbody = base64.b64encode(gzbody).decode()
    resp = {
        "body": b64gzipbody,
        "headers": {
            "Access-Control-Allow-Credentials": "true",
            "Access-Control-Allow-Methods": "GET",
            "Access-Control-Allow-Origin": "*",
            "Content-Encoding": "gzip",
            "Content-Type": "application/json",
        },
        "isBase64Encoded": True,
        "statusCode": 200,
    }
    res = app(event, {})
    assert res == resp

    event = {
        "path": "/test_compress_b64/remotepixel.json",
        "httpMethod": "GET",
        "headers": {},
        "queryStringParameters": {},
    }

    resp = {
        "body": json.dumps({"test": 0}),
        "headers": {
            "Access-Control-Allow-Credentials": "true",
            "Access-Control-Allow-Methods": "GET",
            "Access-Control-Allow-Origin": "*",
            "Content-Type": "application/json",
        },
        "statusCode": 200,
    }
    res = app(event, {})
    assert res == resp


def test_API_otherCompression():
    """Test other compression."""

    body = b"thisisafakeencodedjpeg"
    zlib_compress = zlib.compressobj(9, zlib.DEFLATED, zlib.MAX_WBITS)
    deflate_compress = zlib.compressobj(9, zlib.DEFLATED, -zlib.MAX_WBITS)
    zlibbody = zlib_compress.compress(body) + zlib_compress.flush()
    deflbody = deflate_compress.compress(body) + deflate_compress.flush()

    app = API(name="test")
    funct = Mock(
        __name__="Mock", return_value=Response(StatusCode.OK, "image/jpeg", body)
    )
    app._add_route(
        "/test_deflate/<user>.jpg",
        funct,
        methods=["GET"],
        cors=True,
        payload_compression_method="deflate",
    )
    app._add_route(
        "/test_zlib/<user>.jpg",
        funct,
        methods=["GET"],
        cors=True,
        payload_compression_method="zlib",
    )

    # Zlib
    event = {
        "path": "/test_zlib/remotepixel.jpg",
        "httpMethod": "GET",
        "headers": {"Accept-Encoding": "zlib, gzip, deflate"},
        "queryStringParameters": {},
    }
    resp = {
        "body": zlibbody,
        "headers": {
            "Access-Control-Allow-Credentials": "true",
            "Access-Control-Allow-Methods": "GET",
            "Access-Control-Allow-Origin": "*",
            "Content-Encoding": "zlib",
            "Content-Type": "image/jpeg",
        },
        "statusCode": 200,
    }
    res = app(event, {})
    assert res == resp

    # Deflate
    event = {
        "path": "/test_deflate/remotepixel.jpg",
        "httpMethod": "GET",
        "headers": {"Accept-Encoding": "zlib, gzip, deflate"},
        "queryStringParameters": {},
    }
    resp = {
        "body": deflbody,
        "headers": {
            "Access-Control-Allow-Credentials": "true",
            "Access-Control-Allow-Methods": "GET",
            "Access-Control-Allow-Origin": "*",
            "Content-Encoding": "deflate",
            "Content-Type": "image/jpeg",
        },
        "statusCode": 200,
    }
    res = app(event, {})
    assert res == resp


def test_API_compression_invalid():
    """Test other compression."""
    app = API(name="test")

    def funct(user):
        return Response(StatusCode.OK, "text/plain", "heyyyy")

    entry = app._add_route(
        "/test/<user>",
        funct,
        methods=["GET"],
        cors=True,
        payload_compression_method="gzip",
    )
    entry.compression = "nope"

    event = {
        "path": "/test/remotepixel",
        "httpMethod": "GET",
        "headers": {"Accept-Encoding": "nope"},
        "queryStringParameters": {},
    }
    resp = {
        "body": '{"errorMessage": "Unsupported compression mode: nope"}',
        "headers": {"Content-Type": "application/json"},
        "statusCode": 500,
    }
    res = app(event, {})
    assert res == resp


def test_API_routeURL():
    """Should catch invalid route and parse valid args."""
    app = API(name="test")
    funct = Mock(
        __name__="Mock", return_value=Response(StatusCode.OK, "text/plain", "heyyyy")
    )
    app._add_route("/test/<user>", funct, methods=["GET"], cors=True)

    event = {
        "route": "/users/remotepixel",
        "httpMethod": "GET",
        "headers": {},
        "queryStringParameters": {},
    }
    resp = {
        "body": '{"errorMessage": "Missing or invalid path"}',
        "headers": {"Content-Type": "application/json"},
        "statusCode": 400,
    }
    res = app(event, {})
    assert res == resp

    event = {
        "path": "/users/remotepixel",
        "httpMethod": "GET",
        "headers": {},
        "queryStringParameters": {},
    }
    resp = {
        "body": '{"errorMessage": "No view function for: GET - /users/remotepixel"}',
        "headers": {"Content-Type": "application/json"},
        "statusCode": 400,
    }
    res = app(event, {})
    assert res == resp

    event = {
        "path": "/test/remotepixel",
        "httpMethod": "POST",
        "headers": {},
        "queryStringParameters": {},
    }
    resp = {
        "body": '{"errorMessage": "No view function for: POST - /test/remotepixel"}',
        "headers": {"Content-Type": "application/json"},
        "statusCode": 400,
    }
    res = app(event, {})
    assert res == resp

    event = {
        "path": "/users/remotepixel",
        "httpMethod": "GET",
        "headers": {},
        "queryStringParameters": {},
    }
    resp = {
        "body": '{"errorMessage": "No view function for: GET - /users/remotepixel"}',
        "headers": {"Content-Type": "application/json"},
        "statusCode": 400,
    }
    res = app(event, {})
    assert res == resp

    event = {
        "path": "/test/users/remotepixel",
        "httpMethod": "GET",
        "headers": {},
        "queryStringParameters": {},
    }
    resp = {
        "body": '{"errorMessage": "No view function for: GET - /test/users/remotepixel"}',
        "headers": {"Content-Type": "application/json"},
        "statusCode": 400,
    }
    res = app(event, {})
    assert res == resp

    funct = Mock(
        __name__="Mock", return_value=Response(StatusCode.OK, "text/plain", "heyyyy")
    )
    app._add_route(
        "/test/<string:v>/<uuid:uuid>/<int:z>/<float:x>.<ext>",
        funct,
        methods=["GET"],
        cors=True,
    )

    event = {
        "path": "/test/remotepixel/6b0d1f74-8f81-11e8-83fd-6a0003389b00/1/-1.0.jpeg",
        "httpMethod": "GET",
        "headers": {},
        "queryStringParameters": {},
    }
    resp = {
        "body": "heyyyy",
        "headers": {
            "Access-Control-Allow-Credentials": "true",
            "Access-Control-Allow-Methods": "GET",
            "Access-Control-Allow-Origin": "*",
            "Content-Type": "text/plain",
        },
        "statusCode": 200,
    }
    res = app(event, {})
    assert res == resp
    funct.assert_called_with(
        v="remotepixel",
        uuid="6b0d1f74-8f81-11e8-83fd-6a0003389b00",
        z=1,
        x=-1.0,
        ext="jpeg",
    )

    # Clear logger handlers
    for h in app.log.handlers:
        app.log.removeHandler(h)


def test_API_routeToken(monkeypatch):
    """Validate tokens."""
    monkeypatch.setenv("TOKEN", "yo")

    app = API(name="test")
    funct = Mock(
        __name__="Mock", return_value=Response(StatusCode.OK, "text/plain", "heyyyy")
    )
    app._add_route("/test/<user>", funct, methods=["GET"], cors=True, token=True)

    event = {
        "path": "/test/remotepixel",
        "httpMethod": "GET",
        "headers": {},
        "queryStringParameters": {"access_token": "yo"},
    }
    resp = {
        "body": "heyyyy",
        "headers": {
            "Access-Control-Allow-Credentials": "true",
            "Access-Control-Allow-Methods": "GET",
            "Access-Control-Allow-Origin": "*",
            "Content-Type": "text/plain",
        },
        "statusCode": 200,
    }
    res = app(event, {})
    assert res == resp
    funct.assert_called_with(user="remotepixel")

    event = {
        "path": "/test/remotepixel",
        "httpMethod": "GET",
        "headers": {},
        "queryStringParameters": {"inp": 1, "access_token": "yo"},
    }
    resp = {
        "body": "heyyyy",
        "headers": {
            "Access-Control-Allow-Credentials": "true",
            "Access-Control-Allow-Methods": "GET",
            "Access-Control-Allow-Origin": "*",
            "Content-Type": "text/plain",
        },
        "statusCode": 200,
    }
    res = app(event, {})
    assert res == resp
    funct.assert_called_with(user="remotepixel", inp=1)

    event = {
        "path": "/test/remotepixel",
        "httpMethod": "GET",
        "headers": {},
        "queryStringParameters": {"access_token": "yep"},
    }
    resp = {
        "body": '{"message": "Invalid access token"}',
        "headers": {"Content-Type": "application/json"},
        "statusCode": 500,
    }
    res = app(event, {})
    assert res == resp

    event = {
        "path": "/test/remotepixel",
        "httpMethod": "GET",
        "headers": {},
        "queryStringParameters": {"token": "yo"},
    }
    resp = {
        "body": '{"message": "Invalid access token"}',
        "headers": {"Content-Type": "application/json"},
        "statusCode": 500,
    }
    res = app(event, {})
    assert res == resp

    monkeypatch.delenv("TOKEN", raising=False)

    event = {
        "path": "/test/remotepixel",
        "httpMethod": "GET",
        "headers": {},
        "queryStringParameters": {"access_token": "yo"},
    }
    resp = {
        "body": '{"message": "Invalid access token"}',
        "headers": {"Content-Type": "application/json"},
        "statusCode": 500,
    }
    res = app(event, {})
    assert res == resp

    # Clear logger handlers
    for h in app.log.handlers:
        app.log.removeHandler(h)


def test_API_functionError():
    """Add and parse route."""
    app = API(name="test")
    funct = Mock(__name__="Mock", side_effect=Exception("hey something went wrong"))
    app._add_route("/test/<user>", funct, methods=["GET"], cors=True)

    event = {
        "path": "/test/remotepixel",
        "httpMethod": "GET",
        "headers": {},
        "queryStringParameters": {},
    }
    resp = {
        "body": '{"errorMessage": "hey something went wrong"}',
        "headers": {
            "Access-Control-Allow-Credentials": "true",
            "Access-Control-Allow-Methods": "GET",
            "Access-Control-Allow-Origin": "*",
            "Content-Type": "application/json",
        },
        "statusCode": 500,
    }
    res = app(event, {})
    assert res == resp

    # Clear logger handlers
    for h in app.log.handlers:
        app.log.removeHandler(h)


def test_API_Post():
    """Should work as expected on POST request."""
    app = API(name="test")
    funct = Mock(
        __name__="Mock", return_value=Response(StatusCode.OK, "text/plain", "heyyyy")
    )
    app._add_route("/test/<user>", funct, methods=["GET", "POST"], cors=True)

    event = {
        "path": "/test/remotepixel",
        "httpMethod": "POST",
        "headers": {},
        "queryStringParameters": {},
        "body": b"0001",
    }
    resp = {
        "body": "heyyyy",
        "headers": {
            "Access-Control-Allow-Credentials": "true",
            "Access-Control-Allow-Methods": "GET,POST",
            "Access-Control-Allow-Origin": "*",
            "Content-Type": "text/plain",
        },
        "statusCode": 200,
    }
    res = app(event, {})
    assert res == resp
    funct.assert_called_with(user="remotepixel", body=b"0001")

    event = {
        "path": "/test/remotepixel",
        "httpMethod": "POST",
        "headers": {},
        "queryStringParameters": {},
        "body": "eyJ5byI6ICJ5byJ9",
        "isBase64Encoded": True,
    }
    resp = {
        "body": "heyyyy",
        "headers": {
            "Access-Control-Allow-Credentials": "true",
            "Access-Control-Allow-Methods": "GET,POST",
            "Access-Control-Allow-Origin": "*",
            "Content-Type": "text/plain",
        },
        "statusCode": 200,
    }
    res = app(event, {})
    assert res == resp
    funct.assert_called_with(user="remotepixel", body='{"yo": "yo"}')

    event = {
        "path": "/test/remotepixel",
        "httpMethod": "GET",
        "headers": {},
        "queryStringParameters": {},
    }
    resp = {
        "body": "heyyyy",
        "headers": {
            "Access-Control-Allow-Credentials": "true",
            "Access-Control-Allow-Methods": "GET,POST",
            "Access-Control-Allow-Origin": "*",
            "Content-Type": "text/plain",
        },
        "statusCode": 200,
    }
    res = app(event, {})
    assert res == resp
    funct.assert_called_with(user="remotepixel")

    # Clear logger handlers
    for h in app.log.handlers:
        app.log.removeHandler(h)


def test_API_ctx():
    """Should work as expected and pass ctx and evt to the function."""
    app = API(name="test")

    @app.route("/<id>", methods=["GET"], cors=True)
    @app.pass_event
    @app.pass_context
    def print_id(ctx, evt, id, params=None):
        return Response(
            StatusCode.OK,
            "application/json",
            {"ctx": ctx, "evt": evt, "id": id, "params": params},
        )

    event = {
        "path": "/remotepixel",
        "httpMethod": "GET",
        "headers": {},
        "queryStringParameters": {"params": "1"},
    }
    headers = {
        "Access-Control-Allow-Credentials": "true",
        "Access-Control-Allow-Methods": "GET",
        "Access-Control-Allow-Origin": "*",
        "Content-Type": "application/json",
    }

    res = app(event, {"ctx": "jqtrde"})
    body = res["body"]
    assert res["headers"] == headers
    assert res["statusCode"] == 200
    assert body["id"] == "remotepixel"
    assert body["params"] == "1"
    assert body["evt"] == event
    assert body["ctx"] == {"ctx": "jqtrde"}

    # Clear logger handlers
    for h in app.log.handlers:
        app.log.removeHandler(h)


def test_API_multipleRoute():
    """Should work as expected."""
    app = API(name="test")

    @app.route("/<user>", methods=["GET"], cors=True)
    @app.route("/<user>@<int:num>", methods=["GET"], cors=True)
    def print_id(user, num=None, params=None):
        return Response(
            StatusCode.OK,
            "application/json",
            json.dumps({"user": user, "num": num, "params": params}),
        )

    event = {
        "path": "/remotepixel",
        "httpMethod": "GET",
        "headers": {},
        "queryStringParameters": {},
    }
    headers = {
        "Access-Control-Allow-Credentials": "true",
        "Access-Control-Allow-Methods": "GET",
        "Access-Control-Allow-Origin": "*",
        "Content-Type": "application/json",
    }

    res = app(event, {})
    body = json.loads(res["body"])
    assert res["statusCode"] == 200
    assert res["headers"] == headers
    assert body["user"] == "remotepixel"
    assert not body.get("num")
    assert not body.get("params")

    event = {
        "path": "/remotepixel@1",
        "httpMethod": "GET",
        "headers": {},
        "queryStringParameters": {"params": "1"},
    }

    res = app(event, {})
    body = json.loads(res["body"])
    assert res["statusCode"] == 200
    assert res["headers"] == headers
    assert body["user"] == "remotepixel"
    assert body["num"] == 1
    assert body["params"] == "1"

    # Clear logger handlers
    for h in app.log.handlers:
        app.log.removeHandler(h)


def test_API_doc(openapi_content):
    """Should work as expected."""
    app = API(name="test")

    @app.route("/test", methods=["POST"])
    def _post(body: str) -> Response:
        """Return something."""
        return Response(StatusCode.OK, "text/plain", "Yo")

    @app.route("/<user>", methods=["GET"], tag=["users"], description="a route")
    def _user(user: str) -> Response:
        """Return something."""
        return Response(StatusCode.OK, "text/plain", "Yo")

    @app.route("/<int:num>", methods=["GET"], token=True)
    def _num(num: int) -> Response:
        """Return something."""
        return Response(StatusCode.OK, "text/plain", "yo")

    @app.route("/<user>/<int:num>", methods=["GET"])
    def _userandnum(user: str, num: int) -> Response:
        """Return something."""
        return Response(StatusCode.OK, "text/plain", "yo")

    @app.route("/<user>/<float:num>", methods=["GET"])
    def _options(
        user: str,
        num: float = 1.0,
        opt1: str = "yep",
        opt2: int = 2,
        opt3: float = 2.0,
        **kwargs,
    ) -> Response:
        """Return something."""
        return Response(StatusCode.OK, "text/plain", "yo")

    @app.route("/<user>/<num>", methods=["GET"])
    @app.pass_context
    @app.pass_event
    def _ctx(evt: Dict, ctx: Dict, user: str, num: int) -> Response:
        """Return something."""
        return Response(StatusCode.OK, "text/plain", "yo")

    event = {
        "path": "/openapi.json",
        "httpMethod": "GET",
        "headers": {},
        "queryStringParameters": {},
    }
    headers = {
        "Access-Control-Allow-Credentials": "true",
        "Access-Control-Allow-Methods": "GET",
        "Access-Control-Allow-Origin": "*",
        "Content-Type": "application/json",
    }

    res = app(event, {})
    body = json.loads(res["body"])
    assert res["statusCode"] == 200
    assert res["headers"] == headers
    assert openapi_content == body

    event = {
        "path": "/docs",
        "httpMethod": "GET",
        "headers": {},
        "queryStringParameters": {},
    }
    headers = {
        "Access-Control-Allow-Credentials": "true",
        "Access-Control-Allow-Methods": "GET",
        "Access-Control-Allow-Origin": "*",
        "Content-Type": "text/html",
    }

    res = app(event, {})
    assert res["statusCode"] == 200
    assert res["headers"] == headers

    event = {
        "path": "/redoc",
        "httpMethod": "GET",
        "headers": {},
        "queryStringParameters": {},
    }
    headers = {
        "Access-Control-Allow-Credentials": "true",
        "Access-Control-Allow-Methods": "GET",
        "Access-Control-Allow-Origin": "*",
        "Content-Type": "text/html",
    }

    res = app(event, {})
    assert res["statusCode"] == 200
    assert res["headers"] == headers

    # Clear logger handlers
    for h in app.log.handlers:
        app.log.removeHandler(h)


def test_API_doc_apigw(openapi_apigw_content):
    """Should work as expected if request from api-gateway."""
    app = API(name="test")

    @app.route("/test", methods=["POST"])
    def _post(body: str) -> Response:
        """Return something."""
        return Response(StatusCode.OK, "text/plain", "Yo")

    @app.route("/<user>", methods=["GET"], tag=["users"], description="a route")
    def _user(user: str) -> Response:
        """Return something."""
        return Response(StatusCode.OK, "text/plain", "Yo")

    @app.route("/<int:num>", methods=["GET"], token=True)
    def _num(num: int) -> Response:
        """Return something."""
        return Response(StatusCode.OK, "text/plain", "yo")

    @app.route("/<user>/<int:num>", methods=["GET"])
    def _userandnum(user: str, num: int) -> Response:
        """Return something."""
        return Response(StatusCode.OK, "text/plain", "yo")

    @app.route("/<user>/<float:num>", methods=["GET"])
    def _options(
        user: str,
        num: float = 1.0,
        opt1: str = "yep",
        opt2: int = 2,
        opt3: float = 2.0,
        **kwargs,
    ) -> Response:
        """Return something."""
        return Response(StatusCode.OK, "text/plain", "yo")

    @app.route("/<user>/<num>", methods=["GET"])
    @app.pass_context
    @app.pass_event
    def _ctx(evt: Dict, ctx: Dict, user: str, num: int) -> Response:
        """Return something."""
        return Response(StatusCode.OK, "text/plain", "yo")

    event = {
        "path": "/openapi.json",
        "httpMethod": "GET",
        "headers": {"Host": "afakeapi.execute-api.us-east-1.amazonaws.com"},
        "requestContext": {"stage": "production"},
        "queryStringParameters": {},
    }
    headers = {
        "Access-Control-Allow-Credentials": "true",
        "Access-Control-Allow-Methods": "GET",
        "Access-Control-Allow-Origin": "*",
        "Content-Type": "application/json",
    }

    res = app(event, {})
    body = json.loads(res["body"])
    assert res["statusCode"] == 200
    assert res["headers"] == headers
    assert openapi_apigw_content == body

    event = {
        "path": "/docs",
        "httpMethod": "GET",
        "headers": {"Host": "afakeapi.execute-api.us-east-1.amazonaws.com"},
        "requestContext": {"stage": "production"},
        "queryStringParameters": {},
    }
    headers = {
        "Access-Control-Allow-Credentials": "true",
        "Access-Control-Allow-Methods": "GET",
        "Access-Control-Allow-Origin": "*",
        "Content-Type": "text/html",
    }

    res = app(event, {})
    assert res["statusCode"] == 200
    assert res["headers"] == headers

    # Clear logger handlers
    for h in app.log.handlers:
        app.log.removeHandler(h)


def test_API_docCustomDomain(openapi_custom_content):
    """Should work as expected."""
    app = API(name="test")

    @app.route("/test", methods=["POST"])
    def _post(body: str) -> Response:
        """Return something."""
        return Response(StatusCode.OK, "text/plain", "Yo")

    @app.route("/<user>", methods=["GET"], tag=["users"], description="a route")
    def _user(user: str) -> Response:
        """Return something."""
        return Response(StatusCode.OK, "text/plain", "Yo")

    @app.route("/<int:num>", methods=["GET"], token=True)
    def _num(num: int) -> Response:
        """Return something."""
        return Response(StatusCode.OK, "text/plain", "yo")

    @app.route("/<user>/<int:num>", methods=["GET"])
    def _userandnum(user: str, num: int) -> Response:
        """Return something."""
        return Response(StatusCode.OK, "text/plain", "yo")

    @app.route("/<user>/<float:num>", methods=["GET"])
    def _options(
        user: str,
        num: float = 1.0,
        opt1: str = "yep",
        opt2: int = 2,
        opt3: float = 2.0,
        **kwargs,
    ) -> Response:
        """Return something."""
        return Response(StatusCode.OK, "text/plain", "yo")

    @app.route("/<user>/<num>", methods=["GET"])
    @app.pass_context
    @app.pass_event
    def _ctx(evt: Dict, ctx: Dict, user: str, num: int) -> Response:
        """Return something."""
        return Response(StatusCode.OK, "text/plain", "yo")

    event = {
        "resource": "/{proxy+}",
        "pathParameters": {"proxy": "openapi.json"},
        "path": "/api/openapi.json",
        "httpMethod": "GET",
        "headers": {},
        "queryStringParameters": {},
    }
    headers = {
        "Access-Control-Allow-Credentials": "true",
        "Access-Control-Allow-Methods": "GET",
        "Access-Control-Allow-Origin": "*",
        "Content-Type": "application/json",
    }

    res = app(event, {})
    body = json.loads(res["body"])
    assert res["statusCode"] == 200
    assert res["headers"] == headers
    assert openapi_custom_content == body

    # Clear logger handlers
    for h in app.log.handlers:
        app.log.removeHandler(h)


def test_routeRegex():
    """Add and parse route."""
    app = API(name="test")
    funct_one = Mock(
        __name__="Mock", return_value=Response(StatusCode.OK, "text/plain", "heyyyy")
    )
    funct_two = Mock(
        __name__="Mock", return_value=Response(StatusCode.OK, "text/plain", "yooooo")
    )
    app._add_route(
        "/test/<regex([0-9]{4}):number>/<regex([a-z]{3}):name>",
        funct_two,
        methods=["GET"],
        cors=True,
    )
    app._add_route(
        "/test/<regex([0-9]{4}):number>/<name>",
        funct_one,
        methods=["GET"],
        cors=True,
    )
    event = {
        "path": "/test/1234/pixel",
        "httpMethod": "GET",
        "headers": {},
        "queryStringParameters": {},
    }
    resp = {
        "body": "heyyyy",
        "headers": {
            "Access-Control-Allow-Credentials": "true",
            "Access-Control-Allow-Methods": "GET",
            "Access-Control-Allow-Origin": "*",
            "Content-Type": "text/plain",
        },
        "statusCode": 200,
    }
    res = app(event, {})
    assert res == resp
    funct_one.assert_called_with(number="1234", name="pixel")

    event = {
        "path": "/test/1234/pix",
        "httpMethod": "GET",
        "headers": {},
        "queryStringParameters": {},
    }
    resp = {
        "body": "yooooo",
        "headers": {
            "Access-Control-Allow-Credentials": "true",
            "Access-Control-Allow-Methods": "GET",
            "Access-Control-Allow-Origin": "*",
            "Content-Type": "text/plain",
        },
        "statusCode": 200,
    }
    res = app(event, {})
    assert res == resp
    funct_two.assert_called_with(number="1234", name="pix")

    # Clear logger handlers
    for h in app.log.handlers:
        app.log.removeHandler(h)


def test_routeRegexFailing():
    """Add and parse route."""
    app = API(name="test")
    funct = Mock(
        __name__="Mock", return_value=Response(StatusCode.OK, "text/plain", "yooooo")
    )
    app._add_route(
        r"/test/<regex(user(\d+)?):user>/<sport>",
        funct,
        methods=["GET"],
        cors=True,
    )
    event = {
        "path": "/test/user1234/rugby",
        "httpMethod": "GET",
        "headers": {},
        "queryStringParameters": {},
    }
    with pytest.raises(Exception):
        app(event, {})
        funct.assert_not_called()

    # Clear logger handlers
    for h in app.log.handlers:
        app.log.removeHandler(h)


def testApigwPath():
    """test api call parsing."""
    # resource "/", no apigwg, noproxy, no path mapping
    event = {"path": "/test/1234/pix", "headers": {}}
    p = proxy.ApigwPath(event)
    assert p.path == "/test/1234/pix"
    assert not p.apigw_stage
    assert not p.api_prefix
    assert not p.path_mapping
    assert p.prefix == ""

    event = {"resource": "/", "path": "/test/1234/pix", "headers": {}}
    p = proxy.ApigwPath(event)
    assert p.path == "/test/1234/pix"
    assert not p.apigw_stage
    assert not p.api_prefix
    assert not p.path_mapping
    assert p.prefix == ""

    # resource "proxy+", no apigwg, no path mapping, no api prefix
    event = {
        "resource": "/{proxy+}",
        "pathParameters": {"proxy": "test/1234/pix"},
        "path": "/test/1234/pix",
        "headers": {},
    }
    p = proxy.ApigwPath(event)
    assert p.path == "/test/1234/pix"
    assert not p.apigw_stage
    assert not p.api_prefix
    assert not p.path_mapping
    assert p.prefix == ""

    # resource "proxy+", no apigwg, no path mapping, api prefix (api)
    event = {
        "resource": "/api/{proxy+}",
        "pathParameters": {"proxy": "test/1234/pix"},
        "path": "/api/test/1234/pix",
        "headers": {},
    }
    p = proxy.ApigwPath(event)
    assert p.path == "/test/1234/pix"
    assert not p.apigw_stage
    assert p.api_prefix == "/api"
    assert not p.path_mapping
    assert p.prefix == "/api"

    # resource "proxy+", no apigwg, path mapping (prefix), api prefix (api)
    event = {
        "resource": "/api/{proxy+}",
        "pathParameters": {"proxy": "test/1234/pix"},
        "path": "/prefix/api/test/1234/pix",
        "headers": {},
    }
    p = proxy.ApigwPath(event)
    assert p.path == "/test/1234/pix"
    assert not p.apigw_stage
    assert p.api_prefix == "/api"
    assert p.path_mapping == "/prefix"
    assert p.prefix == "/prefix/api"

    # resource "proxy+", apigwg (production), api prefix (api)
    event = {
        "resource": "/api/{proxy+}",
        "pathParameters": {"proxy": "test/1234/pix"},
        "path": "/prefix/api/test/1234/pix",
        "headers": {"host": "afakeapi.execute-api.us-east-1.amazonaws.com"},
        "requestContext": {"stage": "production"},
    }
    p = proxy.ApigwPath(event)
    assert p.path == "/test/1234/pix"
    assert p.apigw_stage == "production"
    assert p.api_prefix == "/api"
    assert not p.path_mapping
    assert p.prefix == "/production/api"

    # New HTTP API integration
    # by `default` api gateway will deploy the API with a `$default` stage
    # pointing to the `root` host.
    # $default -> https://ggnbmhlvlf.execute-api.us-east-1.amazonaws.com
    # You can then add other stage:
    # $default -> https://ggnbmhlvlf.execute-api.us-east-1.amazonaws.com
    # test -> https://ggnbmhlvlf.execute-api.us-east-1.amazonaws.com/test
    #
    # resource "proxy+", apigwg stage ($default), no path mapping, no api prefix
    event = {
        "version": "1.0",
        "resource": "/{proxy+}",
        "pathParameters": {"proxy": "test/1234/pix"},
        "path": "test/1234/pix",
        "headers": {"host": "afakeapi.execute-api.us-east-1.amazonaws.com"},
        "requestContext": {"stage": "$default"},
    }
    p = proxy.ApigwPath(event)
    assert p.path == "/test/1234/pix"
    assert p.apigw_stage == "$default"
    assert not p.api_prefix
    assert not p.path_mapping
    assert not p.prefix

    # resource "proxy+", apigwg stage (production), no path mapping, no api prefix
    event = {
        "version": "1.0",
        "resource": "/{proxy+}",
        "pathParameters": {"proxy": "test/1234/pix"},
        "path": "test/1234/pix",
        "headers": {"host": "afakeapi.execute-api.us-east-1.amazonaws.com"},
        "requestContext": {"stage": "production"},
    }
    p = proxy.ApigwPath(event)
    assert p.path == "/test/1234/pix"
    assert p.apigw_stage == "production"
    assert not p.api_prefix
    assert not p.path_mapping
    assert p.prefix == "/production"


def testApigwHostUrl():
    """Test url property."""
    app = API(name="test")
    funct = Mock(
        __name__="Mock", return_value=Response(StatusCode.OK, "text/plain", "heyyyy")
    )
    app._add_route("/test/<string:user>/<name>", funct, methods=["GET"], cors=True)

    # resource "/", no apigwg, noproxy, no path mapping
    event = {
        "path": "/test/1234/pix",
        "headers": {"Host": "test.apigw.com"},
        "httpMethod": "GET",
    }
    _ = app(event, {})
    assert app.host == "https://test.apigw.com"

    event = {
        "resource": "/",
        "path": "/test/1234/pix",
        "headers": {"Host": "test.apigw.com"},
        "httpMethod": "GET",
    }
    _ = app(event, {})
    assert app.host == "https://test.apigw.com"

    # resource "proxy+", apigwg (production), api prefix (api)
    event = {
        "resource": "/api/{proxy+}",
        "pathParameters": {"proxy": "test/1234/pix"},
        "path": "/api/test/1234/pix",
        "headers": {
            "X-Forwarded-Host": "abcdefghij.execute-api.eu-central-1.amazonaws.com"
        },
        "requestContext": {"stage": "production"},
        "httpMethod": "GET",
    }
    _ = app(event, {})
    assert (
        app.host
        == "https://abcdefghij.execute-api.eu-central-1.amazonaws.com/production"
    )

    # resource "proxy+", apigwg HTTP ($default)
    event = {
        "version": "1.0",
        "resource": "/{proxy+}",
        "pathParameters": {"proxy": "test/1234/pix"},
        "path": "test/1234/pix",
        "headers": {
            "X-Forwarded-Host": "abcdefghij.execute-api.eu-central-1.amazonaws.com"
        },
        "requestContext": {"stage": "$default"},
        "httpMethod": "GET",
    }
    _ = app(event, {})
    assert app.host == "https://abcdefghij.execute-api.eu-central-1.amazonaws.com"

    # resource "proxy+", no apigwg, no path mapping, no api prefix
    event = {
        "resource": "/{proxy+}",
        "pathParameters": {"proxy": "test/1234/pix"},
        "path": "/test/1234/pix",
        "headers": {"Host": "test.apigw.com"},
        "httpMethod": "GET",
    }
    _ = app(event, {})
    assert app.host == "https://test.apigw.com"

    # resource "proxy+", no apigwg, path mapping (prefix), api prefix (api)
    event = {
        "resource": "/api/{proxy+}",
        "pathParameters": {"proxy": "test/1234/pix"},
        "path": "/prefix/api/test/1234/pix",
        "headers": {"Host": "test.apigw.com"},
        "httpMethod": "GET",
    }

    _ = app(event, {})
    assert app.host == "https://test.apigw.com/prefix"

    # Local
    app.https = False
    event = {
        "resource": "/",
        "path": "/api/test/1234/pix",
        "headers": {"Host": "127.0.0.0:8000"},
        "httpMethod": "GET",
    }

    _ = app(event, {})
    assert app.host == "http://127.0.0.0:8000"


def test_API_simpleRoute():
    """Should work as expected."""
    app = API(name="test")

    @app.post("/test")
    def _post(body: str) -> Response:
        """Return something."""
        return Response(StatusCode.OK, "text/plain", body)

    @app.put("/<user>")
    def _put(user: str, body: str) -> Response:
        """Return something."""
        return Response(StatusCode.OK, "text/plain", body)

    @app.patch("/<user>")
    def _patch(user: str, body: str) -> Response:
        """Return something."""
        return Response(StatusCode.OK, "text/plain", body)

    @app.delete("/<user>")
    def _delete(user: str) -> Response:
        """Return something."""
        return Response(StatusCode.OK, "text/plain", user)

    @app.options("/<user>")
    def _options(user: str) -> Response:
        """Return something."""
        return Response(StatusCode.OK, "text/plain", user)

    @app.head("/<user>")
    def _head(user: str) -> Response:
        """Return something."""
        return Response(StatusCode.OK, "text/plain", user)

    @app.get("/<user>", tag=["users"], description="a route", cors=True)
    def _user(user: str) -> Response:
        """Return something."""
        return Response(StatusCode.OK, "text/plain", user)

    event = {
        "path": "/remotepixel",
        "httpMethod": "GET",
        "headers": {},
        "queryStringParameters": {},
    }
    headers = {
        "Access-Control-Allow-Credentials": "true",
        "Access-Control-Allow-Methods": "GET",
        "Access-Control-Allow-Origin": "*",
        "Content-Type": "text/plain",
    }

    res = app(event, {})
    assert res["statusCode"] == 200
    assert res["headers"] == headers
    assert res["body"] == "remotepixel"

    for method in ["POST", "PUT", "PATCH"]:
        event = {
            "path": "/test",
            "httpMethod": method,
            "headers": {},
            "queryStringParameters": {},
            "body": f"yo {method.lower()}",
        }
        headers = {
            "Content-Type": "text/plain",
        }
        res = app(event, {})
        assert res["statusCode"] == 200
        assert res["headers"] == headers
        assert res["body"] == f"yo {method.lower()}"

    for method in ["DELETE", "OPTIONS", "HEAD"]:
        event = {
            "path": "/test",
            "httpMethod": method,
            "headers": {},
            "queryStringParameters": {},
        }
        headers = {
            "Content-Type": "text/plain",
        }
        res = app(event, {})
        assert res["statusCode"] == 200
        assert res["headers"] == headers
        assert res["body"] == "test"

    # Clear logger handlers
    for h in app.log.handlers:
        app.log.removeHandler(h)
