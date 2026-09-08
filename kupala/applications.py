import contextlib
import typing

import click
from starlette.datastructures import State
from starlette.exceptions import HTTPException
from starlette.middleware import Middleware as ASGIMiddlewareWrapper
from starlette.middleware.errors import ServerErrorMiddleware
from starlette.middleware.exceptions import ExceptionMiddleware
from starlette.requests import HTTPConnection
from starlette.routing import Router
from starlette.types import Lifespan, Receive, Scope, Send

from kupala.dependencies import INVOCATION_CONTEXT_KEY, Binding, InjectionScope, InvocationContext
from kupala.error_handlers import (
    ErrorHandler,
    http_error_handler,
    server_error_handler,
    websocket_error_handler,
)
from kupala.errors import BaseHTTPError
from kupala.middleware import Middleware, WebSocketMiddleware
from kupala.routing import Routes
from kupala.websockets import WebSocketError


class Kupala:
    def __init__(
        self,
        package_name: str,
        *,
        routes: Routes,
        debug: bool = False,
        middleware: typing.Sequence[Middleware] = (),
        websocket_middleware: typing.Sequence[WebSocketMiddleware] = (),
        asgi_middleware: typing.Sequence[ASGIMiddlewareWrapper] = (),
        commands: typing.Sequence[click.Command] = (),
        lifespans: typing.Sequence[Lifespan[Kupala]] = (),
        error_handlers: typing.Mapping[type[Exception], ErrorHandler] | None = None,
    ) -> None:
        self.name = package_name
        self._overrides: typing.Mapping[typing.Any, Binding] = {}
        self.routes = routes
        self.debug = debug
        self.commands = commands
        self.middleware = list(middleware)
        self.websocket_middleware = list(websocket_middleware)
        self.lifespans = list(lifespans)
        self.error_handlers = {
            BaseHTTPError: http_error_handler,
            HTTPException: http_error_handler,
            WebSocketError: websocket_error_handler,
            **(error_handlers or {}),
        }
        # ExceptionMiddleware resolves handlers by MRO, so a catch-all left in this map would match
        # every error and return before ServerErrorMiddleware can re-raise it for the server to log.
        # Starlette splits it out the same way.
        self.server_error_handler = self.error_handlers.pop(Exception, server_error_handler)

        asgi_middleware = [
            ASGIMiddlewareWrapper(ServerErrorMiddleware, handler=self.server_error_handler),
            *asgi_middleware,
            ASGIMiddlewareWrapper(ExceptionMiddleware, handlers=self.error_handlers),
        ]
        app = Router(
            lifespan=self._composed_lifespan,
            routes=routes.compile(
                tuple(self.middleware),
                tuple(self.websocket_middleware),
            ),
        )
        for cls, args, kwargs in reversed(asgi_middleware):
            app = cls(app, *args, **kwargs)
        self._asgi_app = app

    @contextlib.asynccontextmanager
    async def _composed_lifespan(self, app: typing.Self) -> typing.AsyncGenerator[dict[str, typing.Any]]:
        """Enter every registered lifespan, merging what they yield into the state shared by all requests.

        Registration order is startup order and the reverse of shutdown order, so a lifespan may rely on
        everything registered before it. When two lifespans yield the same key, the later one wins.
        """

        state: dict[str, typing.Any] = {}
        async with contextlib.AsyncExitStack() as stack:
            for factory in self.lifespans:
                if partial := await stack.enter_async_context(factory(app)):
                    state.update(partial)

            yield state

    @contextlib.contextmanager
    def override_dependencies(self, overrides: typing.Mapping[typing.Any, Binding]) -> typing.Iterator[None]:
        """Replace dependencies for requests made inside this block, keyed by the annotation they are declared with.

        Intended for tests. The replacements apply to every request the application handles while the
        block is open, so they are not safe to use around concurrent requests.
        """

        previous = self._overrides
        self._overrides = {**previous, **overrides}
        try:
            yield
        finally:
            self._overrides = previous

    def injection_scope(self) -> InjectionScope:
        return InjectionScope(bindings={Kupala: self})

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        injection_scope = self.injection_scope()
        if scope["type"] in ("http", "websocket"):
            injection_scope.bind(HTTPConnection, HTTPConnection(scope, receive))

        context = InvocationContext(
            scope=injection_scope,
            state=State(scope.setdefault("state", {})),
            overrides=self._overrides,
        )

        scope["app"] = self
        scope[INVOCATION_CONTEXT_KEY] = context

        async with context:
            await self._asgi_app(scope, receive, send)

    def cli(self) -> None:
        pass
