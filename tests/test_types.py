"""Test types functionality."""

import pytest

from aws_lambda_proxy import StatusCode
from aws_lambda_proxy.types import Response as ResponseType


def test_response_dataclass_with_headers():
    """Test Response dataclass with custom headers."""
    response = ResponseType(
        status_code=StatusCode.OK,
        content_type="application/json",
        body='{"test": true}',
        headers={"X-Custom": "value"},
    )

    assert response.status_code == StatusCode.OK
    assert response.content_type == "application/json"
    assert response.body == '{"test": true}'
    assert response.headers == {"X-Custom": "value"}


def test_response_dataclass_frozen():
    """Test that Response dataclass is frozen (immutable)."""
    response = ResponseType(
        status_code=StatusCode.OK, content_type="text/plain", body="test"
    )

    # Should raise an error when trying to modify
    with pytest.raises(AttributeError):
        response.status_code = StatusCode.BAD_REQUEST
