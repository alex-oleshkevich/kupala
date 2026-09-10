import contextlib
import typing

import click
import jinja2
from starlette.datastructures import State
from starlette.exceptions import HTTPException
from starlette.middleware import Middleware as ASGIMiddlewareWrapper
from starlette.middleware.errors import ServerErrorMiddleware
from starlette.middleware.exceptions import ExceptionMiddleware
from starlette.requests import HTTPConnection
from starlette.routing import Router
from starlette.types import Lifespan, Receive, Scope, Send

from kupala.binders import DEFAULT_MODEL_BINDERS, ModelBinder
from kupala.commands import Commands
from kupala.dependencies import INVOCATION_CONTEXT_KEY, Binding, InjectionScope, InvocationContext
from kupala.error_handlers import (
    ErrorHandler,
    http_error_handler,
    server_error_handler,
    websocket_error_handler,
)
from kupala.errors import BaseHTTPError
from kupala.extensions import AppBuilder, Extension
from kupala.middleware import Middleware, WebSocketMiddleware
from kupala.routing import Routes
from kupala.templates import Templates
from kupala.websockets import WebSocketError


class Kupala:
    def __init__(
        self,
        package_name: str,
        *,
        routes: Routes | typing.Sequence[Routes] = (),
        debug: bool = False,
        middleware: typing.Sequence[Middleware] = (),
        websocket_middleware: typing.Sequence[WebSocketMiddleware] = (),
        asgi_middleware: typing.Sequence[ASGIMiddlewareWrapper] = (),
        commands: Commands | typing.Sequence[click.Command] = (),
        lifespans: typing.Sequence[Lifespan[Kupala]] = (),
        error_handlers: typing.Mapping[type[Exception], ErrorHandler] | None = None,
        model_binders: typing.Sequence[ModelBinder] = DEFAULT_MODEL_BINDERS,
        extensions: typing.Sequence[Extension] = (),
        templates: Templates | None = None,
    ) -> None:
        self.name = package_name
        self._overrides: typing.Mapping[typing.Any, Binding] = {}
        self.routes = routes if isinstance(routes, Routes) else Routes(children=routes)
        self.debug = debug
        self.commands = commands.compile() if isinstance(commands, Commands) else list(commands)
        self.middleware = list(middleware)
        self.websocket_middleware = list(websocket_middleware)
        self.model_binders = list(model_binders)
        self.lifespans = list(lifespans)
        self.templates = templates or Templates(auto_reload=debug)

        builder = AppBuilder()
        for extension in extensions:
            extension.install(builder)

        self.routes.include(builder.routes)
        self.commands.extend(builder.commands.compile())
        self.lifespans.extend(builder.lifespans)
        self.model_binders.extend(builder.model_binders)
        self.templates.add_filters(builder.template_filters)
        self.templates.add_globals(builder.template_globals)
        self.templates.add_loaders([*builder.template_loaders, jinja2.PackageLoader("kupala")])
        self.templates.add_context_processors(builder.context_processors)

        self.error_handlers = {
            BaseHTTPError: http_error_handler,
            HTTPException: http_error_handler,
            WebSocketError: websocket_error_handler,
            # extensions register before the application, which always has the last word
            **builder.error_handlers,
            **(error_handlers or {}),
        }
        # ExceptionMiddleware resolves handlers by MRO, so a catch-all left in this map would match
        # every error and return before ServerErrorMiddleware can re-raise it for the server to log.
        self.server_error_handler = self.error_handlers.pop(Exception, server_error_handler)

        asgi_middleware = [
            ASGIMiddlewareWrapper(ServerErrorMiddleware, handler=self.server_error_handler),
            *asgi_middleware,
            ASGIMiddlewareWrapper(ExceptionMiddleware, handlers=self.error_handlers),
        ]
        app = Router(
            lifespan=self._composed_lifespan,
            routes=self.routes.compile(
                tuple(self.middleware),
                tuple(self.websocket_middleware),
                tuple(self.model_binders),
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

        state: dict[str, typing.Any] = {"template_renderer": self.templates}
        async with contextlib.AsyncExitStack() as stack:
            for factory in self.lifespans:
                if partial := await stack.enter_async_context(factory(app)):
                    state.update(partial)

            yield state

    def lifespan(self) -> contextlib.AbstractAsyncContextManager[dict[str, typing.Any]]:
        """Start the application outside a server, yielding the state its lifespans contribute.

        The server reaches the same code through the ASGI lifespan protocol; this is the entry point
        for everything else that has to run against a started application, such as the CLI.
        """

        return self._composed_lifespan(self)

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

    def invocation_context(self, state: dict[str, typing.Any]) -> InvocationContext:
        """Build the context one invocation resolves its dependencies from, over the given state."""

        return InvocationContext(
            scope=self.injection_scope(),
            state=State(state),
            overrides=self._overrides,
        )

    def cli(self, args: typing.Sequence[str] | None = None) -> int:
        """Run the command line interface against this application, skipping app discovery."""

        from kupala.cli import main

        return main(args, app=self)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        context = self.invocation_context(scope.setdefault("state", {}))
        if scope["type"] in ("http", "websocket"):
            context.scope.bind(HTTPConnection, HTTPConnection(scope, receive))

        scope["app"] = self
        scope[INVOCATION_CONTEXT_KEY] = context

        async with context:
            await self._asgi_app(scope, receive, send)
