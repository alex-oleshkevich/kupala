from __future__ import annotations

import anyio
import click
import contextvars as cv
import inspect
import logging
import traceback
import typing as t
from contextlib import AsyncExitStack
from starlette.datastructures import State
from starlette.routing import BaseRoute
from starlette.types import ASGIApp, Receive, Scope, Send

from kupala.config import Config
from kupala.console.application import ConsoleApplication
from kupala.container import Container, Resolver
from kupala.contracts import ContextProcessor, Invoker
from kupala.errors import ServerErrorMiddleware
from kupala.exceptions import ErrorHandler, ExceptionMiddleware
from kupala.middleware import Middleware, MiddlewareStack
from kupala.requests import Request
from kupala.responses import Response
from kupala.routing import Router, Routes

if t.TYPE_CHECKING:
    from kupala.providers import Provider

_T = t.TypeVar('_T')


class Kupala:
    def __init__(
        self,
        *,
        debug: bool = None,
        config: t.Mapping = None,
        template_dirs: list[str] = None,
        providers: t.Iterable[t.Union['Provider', t.Type['Provider']]] = None,
        routes: t.Union[Routes, list[BaseRoute]] = None,
        context_processors: list[ContextProcessor] = None,
        commands: list[click.Command] = None,
        error_handlers: dict[t.Union[t.Type[Exception], int], t.Optional[ErrorHandler]] = None,
        middleware: t.Union[list[Middleware], MiddlewareStack] = None,
        lifespan: t.List[t.Callable[[Kupala], t.AsyncContextManager]] = None,
        exception_handler: t.Callable[[Request, Exception], Response] = None,
    ) -> None:
        self.lifespan = lifespan or []
        self.routes = Routes(list(routes) if routes else [])
        self.config = Config(config)
        self.debug = debug
        self.middleware = MiddlewareStack(list(middleware or []))
        self.providers = providers or []
        self.context_processors: t.List[ContextProcessor] = context_processors or []
        self.error_handlers = error_handlers or {}
        self.services = Container()
        self.template_dirs = template_dirs or []
        self.commands = commands or []
        self.exception_handler = exception_handler
        self.state = State()

        self._asgi_app: t.Optional[ASGIApp] = None
        self._router: t.Optional[Router] = None
        self._request_container: cv.ContextVar[Container] = cv.ContextVar('_request_container', default=self.services)
        self._request: cv.ContextVar[t.Optional[Request]] = cv.ContextVar('_current_request')

        self.services.bind(Kupala, self)
        self.services.bind(Container, self.services)
        self.services.bind(Resolver, self.services)
        self.services.bind(Invoker, self.services)
        self.services.bind(Config, self.config)

    async def lifespan_handler(self, scope: Scope, receive: Receive, send: Send) -> None:
        """ASGI lifespan events handler."""
        try:
            await receive()
            async with AsyncExitStack() as stack:
                for hook in self.lifespan:
                    await stack.enter_async_context(hook(self))

                await send({"type": "lifespan.startup.complete"})
                try:
                    await receive()
                except anyio.get_cancelled_exc_class():
                    pass
        except BaseException as ex:
            logging.exception(ex)
            text = traceback.format_exc()
            await send({"type": "lifespan.startup.failed", "message": text})
        else:
            await send({"type": "lifespan.shutdown.complete"})

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        assert scope["type"] in {"http", "websocket", "lifespan"}
        set_current_application(self)

        if self._asgi_app is None:
            self._asgi_app = self._create_app()

        request_container = Container(parent=self.services)
        scope["app"] = self
        scope['resolver'] = request_container
        scope["router"] = self._router

        if scope["type"] == "lifespan":
            await self.lifespan_handler(scope, receive, send)
            return

        if scope["type"] == "http":
            request = Request(scope, receive, send)
            request_container.bind(Request, request)
            scope["request"] = request
            self._request.set(request)

        self._request_container.set(request_container)
        with request_container.change_context({}):
            assert self._asgi_app
            await self._asgi_app(scope, receive, send)

    def cli(self) -> int:
        set_current_application(self)
        app = ConsoleApplication(self.services, self.commands)

        with self.services.change_context({}):
            return app.run()

    def bootstrap(self) -> None:
        providers = [provider() if inspect.isclass(provider) else provider for provider in self.providers]
        self.apply_providers(*providers)

    def apply_providers(self, *providers: Provider) -> None:
        for provider in providers:
            provider.configure(self)
        for provider in providers:
            provider.register(self)
        for provider in providers:
            provider.bootstrap(self)

    def _create_app(self) -> ASGIApp:
        app: ASGIApp = Router(routes=self.routes)
        self._router = t.cast(Router, app)
        self.middleware.use(ExceptionMiddleware, handlers=self.error_handlers)
        self.middleware.top(ServerErrorMiddleware, debug=self.debug, handler=self.exception_handler)
        for mw in reversed(self.middleware):
            app = mw.wrap(app)
        return app

    @t.overload
    def invoke(self, fn_or_class: t.Type[_T], extra_kwargs: t.Dict[str, t.Any] = None) -> _T:
        ...

    @t.overload
    def invoke(self, fn_or_class: t.Callable, extra_kwargs: t.Dict[str, t.Any] = None) -> t.Any:
        ...

    def invoke(self, fn_or_class: t.Union[t.Callable, t.Type], extra_kwargs: t.Dict[str, t.Any] = None) -> t.Any:
        """Resolve callable dependencies and call it passing dependencies to callable arguments.
        If `fn_or_class` is a type then it will be instantiated.

        Use `extra_kwargs` to provide dependency hints to the injector."""
        return self._request_container.get().invoke(fn_or_class, extra_kwargs=extra_kwargs)

    @t.overload
    def resolve(self, key: t.Type[_T]) -> _T:
        ...

    @t.overload
    def resolve(self, key: t.Any) -> t.Any:
        ...

    def resolve(self, key: t.Any) -> t.Any:
        """Resolve a service from the current container."""
        return self._request_container.get().resolve(key)


_current_app: cv.ContextVar[Kupala] = cv.ContextVar('_current_app')


def set_current_application(app: Kupala) -> None:
    _current_app.set(app)


def get_current_application() -> Kupala:
    return _current_app.get()
