"""lambda-proxy: A simple AWS Lambda proxy to handle API Gateway request."""

from http import HTTPStatus as StatusCode

from .proxy import API
from .types import Response
