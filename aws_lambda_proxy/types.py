from dataclasses import dataclass
from typing import Union

from aws_lambda_proxy import StatusCode


@dataclass(frozen=True)
class Response:
    status_code: StatusCode
    content_type: str
    body: Union[str, bytes]
