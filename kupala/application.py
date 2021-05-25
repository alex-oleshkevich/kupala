import logging
import traceback
import typing as t
from contextlib import AsyncExitStack

import click
from starlette.middleware.errors import ServerErrorMiddleware
from starlette.types import ASGIApp, Receive, Scope, Send

from kupala.container import Container

from .config import Config
from .contracts import Debug
from .dotenv import Env
from .extensions import Extension, Extensions
from .middleware import MiddlewareStack
from .requests import Request
from .routing import Router, Routes


class App(Container):
    def __init__(
        self,
        config: dict = None,
        debug: bool = False,
        env_prefix: str = "",
        extensions: list[Extension] = None,
    ) -> None:
        super().__init__()
        self.commands: list[click.Command] = []
        self.config = Config(config)
        self.debug = debug
        self.env = Env(env_prefix)
        self.extensions = Extensions(extensions)
        self.lifecycle: list[t.Callable[[App], t.AsyncContextManager]] = []
        self.middleware = MiddlewareStack()
        self.routes = Routes()

        self._asgi_app_instance: t.Optional[ASGIApp] = None
        self._booted = False

        self.bind(Debug, self.debug, aliases="debug")
        self.bind(App, self, "app")
        self.bind(Env, self.env, "env")
        self.bind(Config, self.config, aliases="config")
        self.bind(Routes, self.routes, aliases="routes")
        self.bind(MiddlewareStack, self.middleware, aliases="middleware")
        self.bind(Extensions, self.extensions, aliases="extensions")

    @property
    def asgi_app(self) -> ASGIApp:
        """Create ASGI application. Once created a cached instance returned."""
        if self._asgi_app_instance is None:
            self._bootstrap()
            app: ASGIApp = self.get(Router)
            self.middleware.use(ServerErrorMiddleware, debug=self.debug)
            for mw in reversed(self.middleware):
                app = mw.wrap(app)
            self._asgi_app_instance = app
        return self._asgi_app_instance

    def run_cli(self) -> None:
        """Run command line application."""
        self._bootstrap()
        app = click.Group()
        for command in self.commands:
            app.add_command(command)
        app()

    async def lifespan(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
    ) -> None:
        """ASGI lifespan events handler."""
        try:
            await receive()
            async with AsyncExitStack() as stack:
                for hook in self.lifecycle:
                    await stack.enter_async_context(hook(self))
                await send({"type": "lifespan.startup.complete"})
                await receive()
        except BaseException as ex:
            logging.exception(ex)
            text = traceback.format_exc()
            await send({"type": "lifespan.startup.failed", "message": text})
            raise
        else:
            await send({"type": "lifespan.shutdown.complete"})

    def _bootstrap(self) -> None:
        if self._booted:
            return

        # register extension services
        for ext in self.extensions:
            ext.register(self)

        # bootstrap extension services
        for ext in self.extensions:
            ext.bootstrap(self)

    async def __call__(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
    ) -> None:
        """ASGI entry point."""
        assert scope["type"] in {"http", "websocket", "lifespan"}

        if scope["type"] == "lifespan":
            await self.lifespan(scope, receive, send)
            return

        scope["app"] = self
        if scope["type"] == "http":
            scope["request"] = Request(scope, receive, send)
        await self.asgi_app(scope, receive, send)
