import typing

from kupala.requests import Request
from kupala.responses import Response

type SyncExceptionHandler = typing.Callable[[Request, BaseException], Response]
type AsyncExceptionHandler = typing.Callable[[Request, BaseException], typing.Awaitable[Response]]
type ExceptionHandler = SyncExceptionHandler | AsyncExceptionHandler


class KupalaError(Exception): ...


class HTTPError(KupalaError):
    status_code: int = 500
    message: str = "Internal Server Error"

    def __init__(
        self,
        message: str | None = None,
        status_code: int | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message or self.message
        self.status_code = status_code or self.status_code
        self.headers = headers


class NotFoundError(HTTPError):
    status_code = 404
    message = "Page not found"
