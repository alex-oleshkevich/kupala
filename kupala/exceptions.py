import inspect
import jinja2
import typing as t
from starlette.concurrency import run_in_threadpool
from starlette.exceptions import HTTPException as BaseHTTPException
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from kupala.requests import Request
from kupala.responses import GoBackResponse, HTMLResponse, JSONResponse, Response


class KupalaError(Exception):
    """Base class for all Kupala framework errors."""


class HTTPException(BaseHTTPException, KupalaError):
    message: t.Optional[str] = None

    def __init__(self, status_code: int, message: str = None) -> None:  # pragma: nocover
        self.message = message or self.message
        super().__init__(status_code=status_code, detail=message)  # type: ignore


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


class ValidationError(KupalaError):
    """Raised when data is not valid by any criteria."""

    def __init__(
        self,
        message: str = None,
        errors: t.Mapping[str, list[str]] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.errors = errors or {}


E = t.TypeVar('E', bound=Exception)
ErrorHandler = t.Callable[[Request, E], t.Any]

_renderer = jinja2.Environment(loader=jinja2.PackageLoader(__name__.split('.')[0]))


async def default_validation_error_handler(request: Request, exc: ValidationError) -> Response:
    if request.wants_json:
        return JSONResponse({'message': exc.message, 'errors': exc.errors}, 400)

    await request.remember_form_data()
    request.set_form_errors(dict(exc.errors or {}))
    response = GoBackResponse(request)
    if exc.message:
        response = response.with_error(exc.message)
    return response


async def default_http_error_handler(request: Request, exc: HTTPException) -> Response:
    if request.wants_json:
        data = {'message': exc.message, 'errors': getattr(exc, 'errors', {})}
        if request.app.debug:
            exception_type = f'{exc.__class__.__module__}.{exc.__class__.__qualname__}'
            data['exception_type'] = exception_type
            data['exception'] = repr(exc)
        return JSONResponse(data, status_code=exc.status_code)
    elif request.app.debug:
        raise exc from None
    else:
        content = _renderer.get_template('errors/http_error.html').render({'request': request, 'exc': exc})
        return HTMLResponse(content, status_code=exc.status_code)


_default_error_handlers = {
    BaseHTTPException: default_http_error_handler,
}


class ErrorHandlers:
    def __init__(self, handlers: dict) -> None:
        self.handlers: dict = {**_default_error_handlers, **handlers}

    def get_for_exception(self, exc: Exception) -> t.Optional[ErrorHandler]:
        class_name = type(exc)
        status_code = exc.status_code if isinstance(exc, BaseHTTPException) else 0
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
