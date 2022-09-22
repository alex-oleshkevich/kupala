import http
import inspect
import logging
import typing
from starlette.concurrency import run_in_threadpool
from starlette.exceptions import HTTPException as BaseHTTPException
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from kupala.http import responses
from kupala.http.exceptions import HTTPException
from kupala.http.requests import Request
from kupala.http.responses import Response

E = typing.TypeVar("E", bound=Exception)
ErrorHandler = typing.Callable[[Request, E], typing.Any]


async def default_http_error_handler(request: Request, exc: HTTPException) -> Response:
    """
    The default error handler for HTTP exception will:

    * reraise exception in debug mode
    * render a default error page if non-debug mode
    """
    if exc.status_code in {204, 304}:
        return Response(status_code=exc.status_code, headers=exc.headers)

    phrase = http.HTTPStatus(exc.status_code).phrase
    return responses.template(
        "errors/http_error.html",
        {"request": request, "phrase": phrase, "status_code": exc.status_code, "message": str(exc)},
        status_code=exc.status_code,
        headers=exc.headers,
    )


async def default_server_error_handler(request: Request, exc: HTTPException) -> Response:
    """The default error handler for 500s."""
    if request.app.debug:
        raise exc from None
    else:
        logging.exception(exc)
        phrase = http.HTTPStatus(500).phrase
        return responses.template(
            "errors/http_error.html",
            {
                "request": request,
                "phrase": phrase,
                "status_code": 500,
            },
            status_code=500,
        )


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

            response = typing.cast(ASGIApp, response)
            await response(scope, receive, sender)
