Lambda-proxy example
--------------------

```
$ git clone https://github.com/layertwo/aws-lambda-proxy.git
$ cd aws-lambda-proxy
$ pip install -U pip
$ pip install -e .

$ cd example

$ python cli.py
```
#### txt


```python
@APP.route(
    "/<user>",
    methods=["GET"],
    cors=True,
)
def main(user):
    """Return JSON Object."""
    return ("OK", "text/plain", user)
```

```
$ curl -i http://127.0.0.1:8000/

    > HTTP/1.0 200 OK
    > Server: BaseHTTP/0.6 Python/3.7.0
    > Date: Tue, 29 Jan 2019 19:54:07 GMT
    > Content-Type: text/plain
    > Access-Control-Allow-Origin: *
    > Access-Control-Allow-Methods: GET
    > Access-Control-Allow-Credentials: true

    YO%
```

##### With multiple routes
```
@APP.route("/<string:user>", methods=["GET"], cors=True)
@APP.route("/<string:user>@<int:num>", methods=["GET"], cors=True)
def main(user, num=0):
    """Return JSON Object."""
    return ("OK", "text/plain", f"{user}-{num}")
```

```
$ curl -i http://127.0.0.1:8000/jqtrde

    jqtrde-0%

$ curl -i http://127.0.0.1:8000/jqtrde@2

    jqtrde-2%
```

#### json

```python
@APP.route(
    "/json",
    methods=["GET"],
    cors=True,
)
def json_handler():
    """Return JSON Object."""
    return ("OK", "application/json", json.dumps({"app": "it works"}))
```

```
$ curl -i http://127.0.0.1:8000/json

    > HTTP/1.0 200 OK
    > Server: BaseHTTP/0.6 Python/3.7.0
    > Date: Tue, 29 Jan 2019 19:55:00 GMT
    > Content-Type: application/json
    > Access-Control-Allow-Origin: *
    > Access-Control-Allow-Methods: GET
    > Access-Control-Allow-Credentials: true

    {"app": "it works"}%
```

## Binary

```python
@APP.route(
    "/binary",
    methods=["GET"],
    cors=True,
    payload_compression_method="gzip",
)
def bin():
    """Return image."""
    with open("./rpix.png", "rb") as f:
        return (
            "OK",
            "image/png",
            f.read()
        )
```

#### Simple
```
curl -v http://127.0.0.1:8000/binary > image.png
    ...
    > GET /binary HTTP/1.1
    > Host: 127.0.0.1:8000
    > User-Agent: curl/7.54.0
    > Accept: */*
    >
    * HTTP 1.0, assume close after body
    < HTTP/1.0 200 OK
    < Server: BaseHTTP/0.6 Python/3.7.0
    < Date: Tue, 29 Jan 2019 19:57:09 GMT
    < Content-Type: image/png
    < Access-Control-Allow-Origin: *
    < Access-Control-Allow-Methods: GET
    < Access-Control-Allow-Credentials: true
    <
    ...
```

#### Compressed
```
$ curl -v --compressed http://127.0.0.1:8000/binary > image.png
    ...
    > GET /binary HTTP/1.1
    > Host: 127.0.0.1:8000
    > User-Agent: curl/7.54.0
    > Accept: */*
    > Accept-Encoding: deflate, gzip
    >
    * HTTP 1.0, assume close after body
    < HTTP/1.0 200 OK
    < Server: BaseHTTP/0.6 Python/3.7.0
    < Date: Tue, 29 Jan 2019 19:56:14 GMT
    < Content-Type: image/png
    < Access-Control-Allow-Origin: *
    < Access-Control-Allow-Methods: GET
    < Access-Control-Allow-Credentials: true
    < Content-Encoding: gzip
    <
```

#### base 64 (api-gateway)

```python
@APP.route(
    "/b64binary",
    methods=["GET"],
    cors=True,
    payload_compression_method="gzip",
    binary_b64encode=True
)
def b64bin():
    """Return base64 encoded image."""
    with open("./rpix.png", "rb") as f:
        return (
            "OK",
            "image/png",
            f.read()
        )
```

```
curl -v http://127.0.0.1:8000/b64binary | base64 --decode > image.png
    ...
    > GET /b64binary HTTP/1.1
    > Host: 127.0.0.1:8000
    > User-Agent: curl/7.54.0
    > Accept: */*
    >
    * HTTP 1.0, assume close after body
    < HTTP/1.0 200 OK
    < Server: BaseHTTP/0.6 Python/3.7.0
    < Date: Tue, 29 Jan 2019 20:07:53 GMT
    < Content-Type: image/png
    < Access-Control-Allow-Origin: *
    < Access-Control-Allow-Methods: GET
    < Access-Control-Allow-Credentials: true
    ...
```
