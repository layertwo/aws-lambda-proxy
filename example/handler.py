"""app: handle requests."""

import json
from typing import Dict

from aws_lambda_proxy import API, StatusCode
from aws_lambda_proxy.types import Response

app = API(name="app", debug=True)


@app.get("/", cors=True)
def main() -> Response:
    """Return JSON Object."""
    return Response(status_code=StatusCode.OK, content_type="text/plain", body="Yo")


@app.get("/<regex([0-9]{2}-[a-zA-Z]{5}):regex1>", cors=True)
def _re_one(regex1: str) -> Response:
    """Return JSON Object."""
    return Response(status_code=StatusCode.OK, content_type="text/plain", body=regex1)


@app.get("/<regex([0-9]{1}-[a-zA-Z]{5}):regex2>", cors=True)
def _re_two(regex2: str) -> Response:
    """Return JSON Object."""
    return Response(status_code=StatusCode.OK, content_type="text/plain", body=regex2)


@app.post("/people", cors=True)
def people_post(body) -> Response:
    """Return JSON Object."""
    return Response(status_code=StatusCode.OK, content_type="text/plain", body=body)


@app.get("/people", cors=True)
def people_get() -> Response:
    """Return JSON Object."""
    return Response(status_code=StatusCode.OK, content_type="text/plain", body="Nope")


@app.get("/<string:user>", cors=True)
@app.get("/<string:user>/<int:num>", cors=True)
def double(user: str, num: int = 0) -> Response:
    """Return JSON Object."""
    return Response(
        status_code=StatusCode.OK, content_type="text/plain", body=f"{user}-{num}"
    )


@app.get("/kw/<string:user>", cors=True)
def kw_method(user: str, **kwargs: Dict) -> Response:
    """Return JSON Object."""
    return Response(
        status_code=StatusCode.OK, content_type="text/plain", body=f"{user}"
    )


@app.get("/ctx/<string:user>", cors=True)
@app.pass_context
@app.pass_event
def ctx_method(evt: Dict, ctx: Dict, user: str, num: int = 0) -> Response:
    """Return JSON Object."""
    return Response(
        status_code=StatusCode.OK, content_type="text/plain", body=f"{user}-{num}"
    )


@app.get("/json", cors=True)
def json_handler() -> Response:
    """Return JSON Object."""
    return Response(
        status_code=StatusCode.OK,
        content_type="application/json",
        body=json.dumps({"app": "it works"}),
    )


@app.get("/binary", cors=True, payload_compression_method="gzip")
def bin() -> Response:
    """Return image."""
    with open("./rpix.png", "rb") as f:
        return Response(
            status_code=StatusCode.OK, content_type="image/png", body=f.read()
        )


@app.get(
    "/b64binary",
    cors=True,
    payload_compression_method="gzip",
    binary_b64encode=True,
)
def b64bin() -> Response:
    """Return base64 encoded image."""
    with open("./rpix.png", "rb") as f:
        return Response(
            status_code=StatusCode.OK, content_type="image/png", body=f.read()
        )
