import logging
import traceback
import typing as t
from contextlib import AsyncExitStack

import click
from starlette.middleware.errors import ServerErrorMiddleware
from starlette.types import ASGIApp, Receive, Scope, Send

from kupala.container import Container

from .middleware import MiddlewareStack
from .requests import Request
from .routing import Router, Routes


class App(Container):
    def __init__(self, debug: bool = False) -> None:
        super().__init__()
        self.debug = debug
        self.middleware = MiddlewareStack()
        self.lifecycle: list[t.AsyncContextManager] = []
        self.routes = Routes()
        self.commands: list[click.Command] = []

        self._router: t.Optional[Router] = None
        self._asgi_app_instance: t.Optional[ASGIApp] = None

    @property
    def asgi_app(self) -> ASGIApp:
        """Create ASGI application. Once created a cached instance returned."""
        if self._asgi_app_instance is None:
            self._router = Router(self.routes)
            app: ASGIApp = self._router
            self.middleware.use(ServerErrorMiddleware, debug=self.debug)
            for mw in reversed(self.middleware):
                app = mw.wrap(app)
            self._asgi_app_instance = app
        return self._asgi_app_instance

    def run_cli(self) -> None:
        """Run command line application."""
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
                    await stack.enter_async_context(hook)
                await send({"type": "lifespan.startup.complete"})
                await receive()
        except BaseException as ex:
            logging.exception(ex)
            text = traceback.format_exc()
            await send({"type": "lifespan.startup.failed", "message": text})
        else:
            await send({"type": "lifespan.shutdown.complete"})

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
