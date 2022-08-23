from __future__ import annotations

import click
import contextvars as cv
import traceback
import typing
from contextlib import AsyncExitStack
from starception import StarceptionMiddleware
from starlette.datastructures import State
from starlette.routing import BaseRoute, Router
from starlette.types import ASGIApp, Receive, Scope, Send

from kupala.console.application import ConsoleApplication
from kupala.contracts import TemplateRenderer
from kupala.exceptions import ShutdownError, StartupError
from kupala.http.middleware import Middleware, MiddlewareStack
from kupala.http.middleware.exception import ErrorHandler, ExceptionMiddleware

_T = typing.TypeVar("_T")


class App:
    state: State

    def __init__(
        self,
        *,
        secret_key: str,
        debug: bool = False,
        routes: typing.Iterable[BaseRoute] | None = None,
        extensions: typing.Iterable[Extension] | None = None,
        commands: typing.Iterable[click.Command] | None = None,
        middleware: typing.Iterable[Middleware] | MiddlewareStack | None = None,
        error_handlers: dict[typing.Type[Exception] | int, ErrorHandler | None] | None = None,
        lifespan_handlers: typing.Iterable[typing.Callable[[App], typing.AsyncContextManager[None]]] = None,
        renderer: TemplateRenderer | None = None,
    ) -> None:
        self.secret_key = secret_key
        self.debug = debug
        self.state = State()

        self._asgi_handler: ASGIApp | None = None
        self.renderer = renderer
        self.routes = routes or []
        self.commands = commands or []
        self.middleware = MiddlewareStack(list(middleware or []))
        self.lifespan_handlers = lifespan_handlers or []
        self.error_handlers = error_handlers or {}
        self._router = Router(list(self.routes))

        # bootstrap extensions
        extensions = extensions or []
        for extension in extensions:
            extension(self)

    async def lifespan_handler(self, scope: Scope, receive: Receive, send: Send) -> None:
        started = False
        try:
            await receive()
            async with AsyncExitStack() as stack:
                for hook in self.lifespan_handlers:
                    await stack.enter_async_context(hook(self))
                await send({"type": "lifespan.startup.complete"})
                started = True
                await receive()
        except BaseException as ex:
            text = traceback.format_exc()
            if started:
                await send({"type": "lifespan.shutdown.failed", "message": text})
                raise ShutdownError(text) from ex
            else:
                await send({"type": "lifespan.startup.failed", "message": text})
                raise StartupError(text) from ex
        else:
            await send({"type": "lifespan.shutdown.complete"})

    def cli(self) -> int:
        """Run console application."""
        set_current_application(self)
        return ConsoleApplication(self, self.commands).run()

    def url_for(self, name: str, **path_params: str) -> str:
        """
        Generate URL by name.

        This method is useful when you want to reverse the URL in non-ASGI mode like CLI. Otherwise, prefer using
        Request.url_for as it generates full URL incl. host and scheme.
        """
        return self._router.url_path_for(name, **path_params)

    def static_url(self, path: str, route_name: str = "static") -> str:
        return self.url_for(route_name, path=path)

    def render(self, template_name: str, context: dict[str, typing.Any] | None = None) -> str:
        """Render template."""
        assert self.renderer, "Template render is not installed."
        return self.renderer.render(template_name, context or {})  # type: ignore[misc]

    def _build_middleware(self) -> ASGIApp:
        middleware = [
            Middleware(StarceptionMiddleware),
            *self.middleware,
            Middleware(ExceptionMiddleware, handlers=self.error_handlers),
        ]

        app: ASGIApp = Router(list(self.routes))
        self._router = app  # type: ignore[assignment]
        for mw in reversed(middleware):
            app = mw.wrap(app)
        return app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        assert scope["type"] in {"http", "websocket", "lifespan"}
        if scope["type"] == "lifespan":
            await self.lifespan_handler(scope, receive, send)
            return

        scope["app"] = self
        scope["state"] = {}
        set_current_application(self)

        try:
            await self._asgi_handler(scope, receive, send)  # type: ignore[misc]
        except TypeError:
            self._asgi_handler = self._build_middleware()
            await self._asgi_handler(scope, receive, send)


class Extension(typing.Protocol):
    def __call__(self, app: App) -> None:
        ...


_current_app: cv.ContextVar[App] = cv.ContextVar("_current_app")


def set_current_application(app: App) -> None:
    _current_app.set(app)


def get_current_application() -> App:
    return _current_app.get()
