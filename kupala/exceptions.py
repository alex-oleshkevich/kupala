import inspect
import jinja2
import typing as t
from starlette.concurrency import run_in_threadpool
from starlette.exceptions import HTTPException as BaseHTTPException
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from kupala.requests import Request
from kupala.responses import HTMLResponse, Response


class HTTPException(BaseHTTPException):
    message: t.Optional[str] = None

    def __init__(self, status_code: int, message: str = None) -> None:  # pragma: nocover
        message = message or self.message
        super().__init__(status_code=status_code, detail=message)


class _BasePredefinedHTTPException(HTTPException):
    status_code: int

    def __init__(self, message: str = None) -> None:
        super().__init__(self.status_code, message)


class BadRequest(_BasePredefinedHTTPException):
    """The server cannot or will not process the request due to an apparent client error
    (e.g., malformed request syntax, size too large, invalid request message framing,
    or deceptive request routing)."""

    status_code = 400


class NotAuthenticated(_BasePredefinedHTTPException):
    """Similar to 403 Forbidden, but specifically for use when authentication is required
    and has failed or has not yet been provided."""

    status_code = 401


class PermissionDenied(_BasePredefinedHTTPException):
    """The request contained valid data and was understood by the server, but the server is refusing action.
    This may be due to the user not having the necessary permissions
    for a resource or needing an account of some sort, or attempting a prohibited action
    (e.g. creating a duplicate record where only one is allowed)."""

    status_code = 403


class PageNotFound(_BasePredefinedHTTPException):
    """The requested resource could not be found but may be available in the future.
    Subsequent requests by the client are permissible."""

    status_code = 404


class MethodNotAllowed(_BasePredefinedHTTPException):
    """A request method is not supported for the requested resource; for example,
    a GET request on a form that requires data to be presented via POST, or a PUT request on a read-only resource."""

    status_code = 405


class NotAcceptable(_BasePredefinedHTTPException):
    """The requested resource is capable of generating only content
    not acceptable according to the Accept headers sent in the request."""

    status_code = 406


class Conflict(_BasePredefinedHTTPException):
    """Indicates that the request could not be processed because of conflict in the current state of the resource,
    such as an edit conflict between multiple simultaneous updates."""

    status_code = 409


class UnsupportedMediaType(_BasePredefinedHTTPException):
    """The request entity has a media type which the server or resource does not support. For example,
    the client uploads an image as image/svg+xml, but the server requires that images use a different format."""

    status_code = 415


class UnprocessableEntity(_BasePredefinedHTTPException):
    """Indicates that the server is unwilling to risk processing a request that might be replayed."""

    status_code = 422


class TooManyRequests(_BasePredefinedHTTPException):
    """The user has sent too many requests in a given amount of time. Intended for use with rate-limiting schemes."""

    status_code = 429


class ValidationError(Exception):
    """Raised when data is not valid by any criteria."""


ErrorHandler = t.Callable[[Request, Exception], t.Any]

_renderer = jinja2.Environment(loader=jinja2.PackageLoader(__name__.split('.')[0]))


async def default_error_handler(request: Request, exc: HTTPException) -> Response:
    content = _renderer.get_template('errors/http_error.html').render({'request': request, 'exc': exc})
    return HTMLResponse(content, status_code=exc.status_code)


_default_error_handlers = {
    BaseHTTPException: default_error_handler,
}


class ErrorHandlers:
    def __init__(self, handlers: dict) -> None:
        self.handlers: dict = {**_default_error_handlers, **handlers}

    def get_for_exception(self, exc: Exception) -> t.Optional[ErrorHandler]:
        class_name = type(exc)
        status_code = 0
        if isinstance(exc, BaseHTTPException):
            status_code = exc.status_code
        if status_code in self.handlers:
            return self.handlers[status_code]

        for cls in class_name.__mro__:
            if cls in self.handlers:
                return self.handlers[cls]

        return None


class ExceptionMiddleware:
    def __init__(self, app: ASGIApp, handlers: t.Dict[t.Union[int, t.Type[Exception]], ErrorHandler]) -> None:
        self.app = app
        self.handlers = ErrorHandlers(handlers)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)

        response_started = False

        async def sender(message: Message) -> None:
            nonlocal response_started

            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(scope, receive, sender)
        except Exception as exc:
            handler = self.handlers.get_for_exception(exc)
            if handler is None:
                raise exc

            if response_started:
                msg = "Caught handled exception, but response already started."
                raise RuntimeError(msg) from exc

            request = Request(scope, receive=receive)
            if inspect.iscoroutinefunction(handler):
                response = await handler(request, exc)
            else:
                response = await run_in_threadpool(handler, request, exc)
            await response(scope, receive, sender)
