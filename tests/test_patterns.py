"""Test patterns functionality."""

from aws_lambda_proxy.patterns import (
    param_pattern,
    params_expr,
    proxy_pattern,
    regex_pattern,
)


def test_patterns_regex_usage():
    """Test that all patterns are working correctly."""
    # Test params_expr
    matches = list(params_expr.finditer("/user/<name>/post/<int:id>"))
    assert len(matches) == 2

    # Test proxy_pattern
    match = proxy_pattern.search("/{proxy+}")
    assert match is not None
    assert match.groupdict()["name"] == "proxy"

    # Test param_pattern
    match = param_pattern.match("<string:username>")
    assert match is not None
    groups = match.groupdict()
    assert groups["type"] == "string"
    assert groups["name"] == "username"

    # Test regex_pattern
    match = regex_pattern.match("<regex([0-9]+):id>")
    assert match is not None
    groups = match.groupdict()
    assert groups["type"] == "regex"
    assert groups["pattern"] == "[0-9]+"
