from dataclasses import dataclass
from typing import Optional, Union

from aws_lambda_proxy import StatusCode


@dataclass(frozen=True)
class Response:
    status_code: StatusCode
    content_type: str
    body: Union[str, bytes]
    headers: Optional[dict[str, str]] = None
