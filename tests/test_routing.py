"""Test routing functionality."""

from aws_lambda_proxy import StatusCode
from aws_lambda_proxy.routing import (
    RouteEntry,
    _converters,
    _path_to_openapi,
    _path_to_regex,
)
from aws_lambda_proxy.types import Response


def test_get_path_args_empty():
    """Test _get_path_args with path that has no parameters."""

    def dummy_endpoint():
        return Response(StatusCode.OK, "text/plain", "test")

    # Route with no parameters
    route = RouteEntry(dummy_endpoint, "/static/path")
    path_args = route._get_path_args()

    # Should return empty list
    assert path_args == []


def test_get_path_args_with_parameters():
    """Test _get_path_args with parameters to ensure line 93 is hit."""

    def dummy_endpoint():
        return Response(StatusCode.OK, "text/plain", "test")

    # Route with parameters
    route = RouteEntry(dummy_endpoint, "/user/<string:name>/<int:id>")
    path_args = route._get_path_args()

    # Should return list of parameter dictionaries
    assert len(path_args) == 2
    assert path_args[0]["name"] == "name"
    assert path_args[0]["type"] == "string"
    assert path_args[1]["name"] == "id"
    assert path_args[1]["type"] == "int"


def test_converters_no_match():
    """Test _converters when param_pattern doesn't match."""
    # Test with malformed path argument that won't match the pattern
    result = _converters("123", "invalid_pattern")
    assert result == "123"  # Should return original value


def test_converters_string_types():
    """Test _converters with string and uuid types."""
    # Test string type
    result = _converters("test_value", "<string:param>")
    assert result == "test_value"

    # Test uuid type
    uuid_value = "550e8400-e29b-41d4-a716-446655440000"
    result = _converters(uuid_value, "<uuid:id>")
    assert result == uuid_value


def test_routing_get_path_args_return():
    """Test _get_path_args to ensure line 93 is hit."""

    def dummy_endpoint():
        return Response(StatusCode.OK, "text/plain", "test")

    # Route with multiple different parameter types to fully exercise the method
    route = RouteEntry(dummy_endpoint, "/api/<string:version>/<int:id>/<uuid:guid>")
    path_args = route._get_path_args()

    # This should hit line 93 (return args)
    assert len(path_args) == 3
    assert all(isinstance(arg, dict) for arg in path_args)
    assert path_args[0]["name"] == "version"
    assert path_args[1]["name"] == "id"
    assert path_args[2]["name"] == "guid"


def test_routing_get_path_args_direct():
    """Test _get_path_args directly to hit line 93."""

    def dummy_endpoint():
        return Response(StatusCode.OK, "text/plain", "test")

    # Test with regex parameter to hit all path parsing logic
    route = RouteEntry(dummy_endpoint, "/api/<regex([a-z]+):slug>/<uuid:id>")

    # Directly call _get_path_args to ensure line 93 coverage
    path_args = route._get_path_args()

    # Verify the return value (line 93)
    assert isinstance(path_args, list)
    assert len(path_args) == 2

    # Verify the structure
    slug_arg = path_args[0]
    assert slug_arg["name"] == "slug"
    assert slug_arg["type"] == "regex"
    assert slug_arg["pattern"] == "[a-z]+"

    id_arg = path_args[1]
    assert id_arg["name"] == "id"
    assert id_arg["type"] == "uuid"


def test_routing_edge_cases():
    """Test various routing edge cases to ensure complete coverage."""
    # Test _path_to_regex with complex pattern
    regex_path = _path_to_regex("/user/<regex([0-9a-f]{32}):token>/data")
    assert "([0-9a-f]{32})" in regex_path

    # Test _path_to_openapi with regex pattern
    openapi_path = _path_to_openapi("/user/<regex([0-9a-f]{32}):token>/data")
    assert "{token}" in openapi_path

    # Test more complex routing scenarios
    def test_func():
        return Response(StatusCode.OK, "text/plain", "test")

    # Test with mixed parameter types
    route = RouteEntry(
        test_func, "/complex/<int:year>/<string:month>/<regex([0-9]{1,2}):day>"
    )
    args = route._get_path_args()

    # This should definitely hit the return statement on line 93
    assert len(args) == 3
    assert args[0]["type"] == "int"
    assert args[1]["type"] == "string"
    assert args[2]["type"] == "regex"


def test_line_93_coverage_direct():
    """Direct test to ensure line 93 in routing.py gets covered."""

    def endpoint():
        return Response(StatusCode.OK, "text/plain", "OK")

    # Test the exact scenario that should hit line 93
    route = RouteEntry(endpoint, "/test/<param>")

    # Call the method multiple times to ensure coverage
    result1 = route._get_path_args()
    result2 = route._get_path_args()

    # Both calls should return the same thing and hit line 93
    assert result1 == result2
    assert len(result1) == 1
    assert result1[0]["name"] == "param"

    # Test with no parameters too
    route_no_params = RouteEntry(endpoint, "/static")
    result_empty = route_no_params._get_path_args()
    assert result_empty == []

    # Test with multiple complex parameters
    route_complex = RouteEntry(
        endpoint,
        "/api/v1/<string:version>/<int:id>/<uuid:guid>/<regex([a-f0-9]+):hash>",
    )
    result_complex = route_complex._get_path_args()

    # Verify the result structure to ensure the method completed successfully
    assert len(result_complex) == 4
    for arg in result_complex:
        assert "name" in arg
        assert "type" in arg

    # Test with regex pattern containing special characters
    route_special = RouteEntry(endpoint, "/search/<regex([a-zA-Z0-9._%-]+):query>")
    result_special = route_special._get_path_args()
    assert len(result_special) == 1
    assert result_special[0]["name"] == "query"
    assert result_special[0]["type"] == "regex"
