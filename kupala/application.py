from __future__ import annotations

import click
import contextvars as cv
import traceback
import typing
from contextlib import AsyncExitStack
from starception import StarceptionMiddleware
from starlette.datastructures import State
from starlette.types import ASGIApp, Receive, Scope, Send

from kupala.console.application import ConsoleApplication
from kupala.contracts import TemplateRenderer
from kupala.di import InjectionRegistry
from kupala.exceptions import ShutdownError, StartupError
from kupala.http.context_processors import standard_processors
from kupala.http.middleware import Middleware, MiddlewareStack
from kupala.http.middleware.exception import ErrorHandler, ExceptionMiddleware
from kupala.http.protocols import ContextProcessor
from kupala.http.routing import Router, Routes


class App:
    state: State

    def __init__(
        self,
        *,
        secret_key: str,
        routes: Routes,
        dependencies: InjectionRegistry | None = None,
        debug: bool = False,
        commands: list[click.Command] | None = None,
        context_processors: list[ContextProcessor] | None = None,
        middleware: list[Middleware] | MiddlewareStack | None = None,
        error_handlers: dict[typing.Type[Exception] | int, typing.Optional[ErrorHandler]] | None = None,
        lifespan_handlers: list[typing.Callable[[App], typing.AsyncContextManager[None]]] = None,
    ) -> None:
        self.secret_key = secret_key
        self.debug = debug
        self.state = State()

        self._router = Router(routes)
        self._commands = commands or []
        self._middleware = MiddlewareStack(list(middleware or []))
        self._lifespan_handlers = lifespan_handlers or []
        self._error_handlers = error_handlers or {}
        self._asgi_handler = self._build_middleware()
        self.context_processors = context_processors or []
        self.context_processors.append(standard_processors)
        self.dependencies = dependencies or InjectionRegistry()

        self.dependencies.bind(self.__class__, self)

    async def lifespan_handler(self, scope: Scope, receive: Receive, send: Send) -> None:
        started = False
        try:
            await receive()
            async with AsyncExitStack() as stack:
                for hook in self._lifespan_handlers:
                    await stack.enter_async_context(hook(self))
                await send({'type': 'lifespan.startup.complete'})
                started = True
                await receive()
        except BaseException as ex:
            text = traceback.format_exc()
            if started:
                await send({'type': 'lifespan.shutdown.failed', 'message': text})
                raise ShutdownError(text) from ex
            else:
                await send({'type': 'lifespan.startup.failed', 'message': text})
                raise StartupError(text) from ex
        else:
            await send({'type': 'lifespan.shutdown.complete'})

    def cli(self) -> int:
        """Run console application."""
        set_current_application(self)
        return ConsoleApplication(self, self._commands).run()

    def url_for(self, name: str, **path_params: str) -> str:
        """
        Generate URL by name.

        This method is useful when you want to reverse the URL in non-ASGI mode
        like CLI. Otherwise, prefer using Request.url_for as it generates full
        URL incl. host and scheme.
        """
        return self._router.url_path_for(name, **path_params)

    def static_url(self, path: str, path_name: str = 'static') -> str:
        return self.url_for(path_name, path=path)

    def render(self, template_name: str, context: dict[str, typing.Any] | None = None) -> str:
        """Render template."""
        return self.dependencies.get(TemplateRenderer).render(template_name, context or {})  # type: ignore[misc]

    def _build_middleware(self) -> ASGIApp:
        self._middleware.top(ExceptionMiddleware, handlers=self._error_handlers, debug=self.debug)
        self._middleware.top(StarceptionMiddleware)

        app: ASGIApp = self._router
        for mw in reversed(self._middleware):
            app = mw.wrap(app)
        return app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        assert scope['type'] in {'http', 'websocket', 'lifespan'}
        if scope['type'] == 'lifespan':
            await self.lifespan_handler(scope, receive, send)
            return

        scope['app'] = self
        scope['state'] = {}
        set_current_application(self)
        await self._asgi_handler(scope, receive, send)


_current_app: cv.ContextVar[App] = cv.ContextVar('_current_app')


def set_current_application(app: App) -> None:
    _current_app.set(app)


def get_current_application() -> App:
    return _current_app.get()
