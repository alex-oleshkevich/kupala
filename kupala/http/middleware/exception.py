import inspect
import jinja2
import typing
from starlette.concurrency import run_in_threadpool
from starlette.exceptions import HTTPException as BaseHTTPException
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from kupala.http.exceptions import HTTPException
from kupala.http.requests import Request
from kupala.http.responses import HTMLResponse, Response

E = typing.TypeVar("E", bound=Exception)
ErrorHandler = typing.Callable[[Request, E], typing.Any]
_renderer = jinja2.Environment(loader=jinja2.PackageLoader(__name__.split(".")[0]))


async def default_http_error_handler(request: Request, exc: HTTPException) -> Response:
    """
    The default error handler for HTTP exception will:

    * reraise exception in debug mode
    * render a default error page if non-debug mode
    """
    if request.app.debug:
        raise exc from None
    else:
        content = _renderer.get_template("errors/http_error.html").render({"request": request, "exc": exc})
        return HTMLResponse(content, status_code=exc.status_code)


_default_error_handlers = {
    BaseHTTPException: default_http_error_handler,
}


class ErrorHandlers:
    def __init__(self, handlers: dict) -> None:
        self.handlers: dict = {**_default_error_handlers, **handlers}

    def get_for_exception(self, exc: Exception) -> ErrorHandler | None:
        class_name = type(exc)
        status_code = exc.status_code if isinstance(exc, BaseHTTPException) else 0
        if status_code in self.handlers:
            return self.handlers[status_code]

        for cls in class_name.__mro__:
            if cls in self.handlers:
                return self.handlers[cls]

        return None


class ExceptionMiddleware:
    def __init__(
        self,
        app: ASGIApp,
        handlers: dict[int | typing.Type[Exception], ErrorHandler],
    ) -> None:
        self.app = app
        self.handlers = ErrorHandlers(handlers)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
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
