import logging
import traceback
import typing as t
from contextlib import AsyncExitStack

import click
from starlette.middleware.errors import ServerErrorMiddleware
from starlette.types import ASGIApp, Receive, Scope, Send

from kupala.container import Container

from .config import Config
from .dotenv import Env
from .extensions import Extensions
from .middleware import MiddlewareStack
from .requests import Request
from .routing import Router, Routes


class App(Container):
    def __init__(
        self,
        config: dict = None,
        debug: bool = False,
        env_prefix: str = "",
    ) -> None:
        super().__init__()
        self.commands: list[click.Command] = []
        self.config = Config(config)
        self.debug = debug
        self.env = Env(env_prefix)
        self.extensions = Extensions()
        self.lifecycle: list[t.Callable[[App], t.AsyncContextManager]] = []
        self.middleware = MiddlewareStack()
        self.routes = Routes()

        self._router: t.Optional[Router] = None
        self._asgi_app_instance: t.Optional[ASGIApp] = None
        self._booted = False

        self.bind(Config, self.config, aliases="config")
        self.bind("debug", self.debug)

    @property
    def asgi_app(self) -> ASGIApp:
        """Create ASGI application. Once created a cached instance returned."""
        if self._asgi_app_instance is None:
            self._bootstrap()
            self._router = Router(self.routes)
            app: ASGIApp = self._router
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
