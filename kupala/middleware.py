import typing

from kupala.requests import Request
from kupala.responses import Response

type CallNext = typing.Callable[[Request], typing.Awaitable[Response]]
type Middleware = typing.Callable[[Request], CallNext]
