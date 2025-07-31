import json
import os
from unittest.mock import Mock

import pytest


@pytest.fixture
def openapi_content():
    json_api = os.path.join(os.path.dirname(__file__), "fixtures", "openapi.json")
    with open(json_api, "r") as f:
        return json.loads(f.read())


@pytest.fixture
def openapi_custom_content():
    json_api_custom = os.path.join(
        os.path.dirname(__file__), "fixtures", "openapi_custom.json"
    )
    with open(json_api_custom, "r") as f:
        return json.loads(f.read())


@pytest.fixture
def openapi_apigw_content():
    json_apigw = os.path.join(
        os.path.dirname(__file__), "fixtures", "openapi_apigw.json"
    )
    with open(json_apigw, "r") as f:
        return json.loads(f.read())


@pytest.fixture
def funct():
    """Mock function for testing purposes."""
    return Mock(__name__="Mock")
