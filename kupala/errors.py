import asyncio
import typing as t

from starlette import exceptions
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from kupala.requests import Request
from kupala.responses import Response, TemplateResponse, TextResponse

ErrorHandler = t.Callable[
    [Request, Exception],
    t.Union[Response, t.Awaitable[Response]],
]


def error_handler_factory(template: str) -> ErrorHandler:
    """Create a error handler callable for Jinja2 template."""

    def view(request: Request, exc: Exception) -> Response:
        return TemplateResponse(
            request,
            template,
            {
                "request": request,
                "exc": exc,
            },
        )

    return view


class ErrorHandlers:
    """A registry of errors handlers."""

    def __init__(self) -> None:
        self._handlers: dict[
            t.Union[int, t.Type[Exception]],
            ErrorHandler,
        ] = {}

    def use(
        self,
        code_or_exc: t.Union[int, t.Type[Exception]],
        handler: t.Union[ErrorHandler, str],
    ) -> None:
        """Add an error handler.
        You can pass either integer representing an HTTP status code
        or an exception class.
        The handler is a view function that accepts request
        and raised exception and returns a response."""
        if isinstance(handler, str):
            self._handlers[code_or_exc] = error_handler_factory(handler)
        else:
            self._handlers[code_or_exc] = handler

    def get(self, exc: Exception) -> t.Optional[ErrorHandler]:
        """Get an error handler for an exception."""
        if isinstance(exc, exceptions.HTTPException):
            handler = self._handlers.get(exc.__class__)
            if handler is None:
                handler = self._handlers.get(exc.status_code, self.http_handler)
            return handler

        handler = self._handlers.get(exc.__class__)
        if handler:
            return handler

        for cls in type(exc).__mro__:
            if cls in self._handlers:
                return self._handlers[cls]
        return None

    def http_handler(self, request: Request, exc: Exception) -> Response:
        """For HTTP errors we display a simple text message
        and set a correct HTTP response status."""
        assert isinstance(exc, exceptions.HTTPException)
        if exc.status_code in {204, 304}:
            return Response(b"", status_code=exc.status_code)
        return TextResponse(exc.detail, exc.status_code)


class ExceptionMiddleware:
    def __init__(self, app: ASGIApp, handlers: ErrorHandlers):
        self.app = app
        self.handlers = handlers

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":  # pragma: nocover
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
            handler = self.handlers.get(exc)
            if handler is None:
                raise exc from None

            if response_started:
                msg = "Caught handled exception, but response already started."
                raise RuntimeError(msg) from exc

            request = scope["request"]
            if asyncio.iscoroutinefunction(handler):
                # todo: fix typing error
                response = await handler(request, exc)  # type: ignore
            else:
                response = await asyncio.to_thread(handler, request, exc)
            await response(scope, receive, sender)
