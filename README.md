# aws-lambda-proxy

![GitHub License](https://img.shields.io/github/license/layertwo/aws-lambda-proxy)
[![Packaging status](https://img.shields.io/pypi/v/aws-lambda-proxy)](https://pypi.org/project/aws-lambda-proxy/)
![PyPI - Python Version](https://img.shields.io/pypi/pyversions/aws-lambda-proxy)
![Build status](https://img.shields.io/github/actions/workflow/status/layertwo/aws-lambda-proxy/python-package.yml?branch=main)
![PyPI - Downloads](https://img.shields.io/pypi/dm/aws-lambda-proxy)

Forked from https://github.com/vincentsarago/lambda-proxy/

A zero-requirement proxy linking AWS API Gateway `{proxy+}` requests and AWS Lambda.

<img width="600" alt="" src="https://user-images.githubusercontent.com/10407788/58742966-6ff50480-83f7-11e9-81f7-3ba7aa2310bb.png">

## Install

```bash
$ pip install -U pip
$ pip install aws-lambda-proxy
```

Or install from source:

```bash
$ git clone https://github.com/layertwo/aws-lambda-proxy.git
$ cd aws-lambda-proxy
$ pip install -U pip
$ pip install -e .
```

# Usage

Lambda proxy is designed to work well with both API Gateway's REST API and the
newer and cheaper HTTP API. If you have issues using with the HTTP API, please
open an issue.

With GET request

```python
from aws_lambda_proxy import API, Response, StatusCode

APP = API(name="app")

@APP.route('/test/tests/<id>', methods=['GET'], cors=True)
def print_id(id):
    return Response(status_code=StatusCode.OK, content_type='plain/text', body=id)
```

With POST request

```python
from aws_lambda_proxy import API, Response, StatusCode

APP = API(name="app")

@APP.route('/test/tests/<id>', methods=['POST'], cors=True)
def print_id(id, body):
    return Response(status_code=StatusCode.OK, content_type='plain/text', body=id)
```

## Binary body

```python
from aws_lambda_proxy import API

APP = API(name="app")

@APP.route('/test', methods=['POST'])
def print_id(body):
    body = json.loads(body)
```

# Routes

Route schema is simmilar to the one used in [Flask](http://flask.pocoo.org/docs/1.0/api/#url-route-registrations)

> Variable parts in the route can be specified with angular brackets `/user/<username>`. By default a variable part in the URL accepts any string without a slash however a different converter can be specified as well by using `<converter:name>`.

Converters:
- `int`: integer
- `string`: string
- `float`: float number
- `uuid`: UUID

example:
- `/app/<user>/<id>` (`user` and `id` are variables)
- `/app/<string:value>/<float:num>` (`value` will be a string, while `num` will be a float)

## Regex
You can also add regex parameters descriptions using special converter `regex()`

example:
```python
@APP.get("/app/<regex([a-z]+):regularuser>")
def print_user(regularuser):
    return Response(status_code=StatusCode.OK, content_type='plain/text', body=f"regular {regularuser}")

@APP.get("/app/<regex([A-Z]+):capitaluser>")
def print_user(capitaluser):
    return Response(status_code=StatusCode.OK, content_type='plain/text', body=f"CAPITAL {capitaluser}")
```

#### Warning

when using **regex()** you must use different variable names or the route might not show up in the documentation.

```python
@APP.get("/app/<regex([a-z]+):user>")
def print_user(user):
    return Response(status_code=StatusCode.OK, content_type='plain/text', body=f"regular {user}")

@APP.get("/app/<regex([A-Z]+):user>")
def print_user(user):
    return Response(status_code=StatusCode.OK, content_type='plain/text', body=f"CAPITAL {user}")
```
This app will work but the documentation will only show the second route because in `openapi.json`, route names will be `/app/{user}` for both routes.

# Route Options

- **path**: the URL rule as string
- **methods**: list of HTTP methods allowed, default: ["GET"]
- **cors**: allow CORS, default: `False`
- **token**: set `access_token` validation
- **payload_compression_method**: Enable and select an output body compression
- **binary_b64encode**: base64 encode the output body (API Gateway)
- **ttl**: Cache Control setting (Time to Live) 
- **cache_control**: Cache Control setting
- **description**: route description (for documentation)
- **tag**: list of tags (for documentation)

## Cache Control

Add a Cache Control header with a Time to Live (TTL) in seconds.

```python
from aws_lambda_proxy import API, Response, StatusCode
APP = API(app_name="app")

@APP.get('/test/tests/<id>', cors=True, cache_control="public,max-age=3600")
def print_id(id):
   return Response(status_code=StatusCode.OK, content_type='plain/text', body=id)
```

Note: If function returns other then "OK", Cache-Control will be set to `no-cache`

## Binary responses

When working with binary on API-Gateway we must return a base64 encoded string

```python
from aws_lambda_proxy import API, Response, StatusCode

APP = API(name="app")

@APP.get('/test/tests/<filename>.jpg', cors=True, binary_b64encode=True)
def print_id(filename):
    with open(f"{filename}.jpg", "rb") as f:
        return Response(status_code=StatusCode.OK, content_type='image/jpeg', body=f.read())
```

## Compression

Enable compression if "Accept-Encoding" if found in headers.

```python
from aws_lambda_proxy import API, Response, StatusCode

APP = API(name="app")

@APP.get(
   '/test/tests/<filename>.jpg',
   cors=True,
   binary_b64encode=True,
   payload_compression_method="gzip"
)
def print_id(filename):
    with open(f"{filename}.jpg", "rb") as f:
       return Response(status_code=StatusCode.OK, content_type='image/jpeg', body=f.read())
```

## Simple Auth token

Lambda-proxy provide a simple token validation system.

-  a "TOKEN" variable must be set in the environment
-  each request must provide a "access_token" params (e.g curl
   http://myurl/test/tests/myid?access_token=blabla)

```python
from aws_lambda_proxy import API, Response, StatusCode

APP = API(name="app")

@APP.get('/test/tests/<id>', cors=True, token=True)
def print_id(id):
    return Response(status_code=StatusCode.OK, content_type='plain/text', body=id)
```

## URL schema and request parameters

QueryString parameters are passed as function's options.

```python
from aws_lambda_proxy import API, Response, StatusCode

APP = API(name="app")

@APP.get('/<id>', cors=True)
def print_id(id, name=None):
    return Response(status_code=StatusCode.OK, content_type='plain/text', body=f"{id}{name}")
```

requests:

```bash
$ curl /000001
   0001

$ curl /000001?name=layertwo
   0001layertwo
```

## Multiple Routes

```python
from aws_lambda_proxy import API, Response, StatusCode
APP = API(name="app")

@APP.get('/<id>', cors=True)
@APP.get('/<id>/<int:number>', cors=True)
def print_id(id, number=None, name=None):
    return Response(status_code=StatusCode.OK, content_type='plain/text', body=f"{id}-{name}-{number}")
```
requests:

```bash

$ curl /000001
   0001--

$ curl /000001?name=layertwo
   0001-layertwo-

$ curl /000001/1?name=layertwo
   0001-layertwo-1
```

# Advanced features

## Context and Event passing

Pass event and context to the handler function.

```python
from aws_lambda_proxy import API, Response, StatusCode

APP = API(name="app")

@APP.get("/<id>", cors=True)
@APP.pass_event
@APP.pass_context
def print_id(ctx, evt, id):
    print(ctx)
    print(evt)
    return Response(status_code=StatusCode.OK, content_type='plain/text', body=f"{id}")
```

# Automatic OpenAPI documentation

By default the APP (`aws_lambda_proxy.API`) is provided with three (3) routes:
- `/openapi.json`: print OpenAPI JSON definition

- `/docs`: swagger html UI
![swagger](https://user-images.githubusercontent.com/10407788/58707335-9cbb0480-8382-11e9-927f-8d992cf2531a.jpg)

- `/redoc`: Redoc html UI
![redoc](https://user-images.githubusercontent.com/10407788/58707338-9dec3180-8382-11e9-8dec-18173e39258f.jpg)

**Function annotations**

To be able to render full and precise API documentation, aws_lambda_proxy uses python type hint and annotations [link](https://www.python.org/dev/peps/pep-3107/).

```python
from aws_lambda_proxy import API, Response, StatusCode 

APP = API(name="app")

@APP.route('/test/<int:id>', methods=['GET'], cors=True)
def print_id(id: int, num: float = 0.2) -> Response:
    return Response(status_code=StatusCode.OK, content_type='plain/text', body=id)
```

In the example above, our route `/test/<int:id>` define an input `id` to be a `INT`, while we also add this hint to the function `print_id` we also specify the type (and default) of the `num` option.

# Custom Domain and path mapping

Note: When using path mapping other than `root` (`/`), `/` route won't be available.

```python
from aws_lambda_proxy import API, Response, StatusCode 

api = API(name="api", debug=True)


# This route won't work when using path mapping
@api.get("/", cors=True)
# This route will work only if the path mapping is set to /api
@api.get("/api", cors=True)
def index():
    html = """<!DOCTYPE html>
    <html>
        <header><title>This is title</title></header>
        <body>
            Hello world
        </body>
    </html>"""
    return Response(status_code=StatusCode.OK, content_type="text/html", body=html)


@api.get("/yo", cors=True)
def yo():
    return Response(status_code=StatusCode.OK, content_type="text/plain", body="YOOOOO")
```

# Examples

-  https://github.com/layertwo/aws-lambda-proxy/tree/main/example


# Contribution & Development

Issues and pull requests are more than welcome.

**Dev install & Pull-Request**

```bash
$ git clone https://github.com/layertwo/aws-lambda-proxy.git
$ cd aws-lambda-proxy
$ pip install -e .[test]
```

### License

See [LICENSE.txt](LICENSE.txt).
