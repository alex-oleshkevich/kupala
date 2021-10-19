from __future__ import annotations

import contextvars
import logging
import traceback
import typing as t
from contextlib import AsyncExitStack
from starlette.exceptions import ExceptionMiddleware
from starlette.middleware.errors import ServerErrorMiddleware
from starlette.routing import BaseRoute
from starlette.types import ASGIApp, Receive, Scope, Send

from kupala.config import Config
from kupala.middleware import MiddlewareStack
from kupala.requests import Request
from kupala.routing import Router, Routes


class Kupala:
    def __init__(self, routes: t.Union[Routes, t.List[BaseRoute]] = None) -> None:
        self.lifespan: t.List[t.Callable[[Kupala], t.AsyncContextManager]] = []
        self._asgi_app: t.Optional[ASGIApp] = None
        self.routes = Routes(list(routes) if routes else [])
        self.config = Config()
        self.middleware = MiddlewareStack()

    async def lifespan_handler(self, scope: Scope, receive: Receive, send: Send) -> None:
        """ASGI lifespan events handler."""
        self.bootstrap()
        await receive()
        try:
            async with AsyncExitStack() as stack:
                for hook in self.lifespan:
                    await stack.enter_async_context(hook(self))

                await send({"type": "lifespan.startup.complete"})
                await receive()
        except BaseException as ex:
            logging.exception(ex)
            text = traceback.format_exc()
            await send({"type": "lifespan.startup.failed", "message": text})
        else:
            await send({"type": "lifespan.shutdown.complete"})

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        assert scope["type"] in {"http", "websocket", "lifespan"}
        scope["app"] = self
        set_current_application(self)

        if scope["type"] == "lifespan":
            await self.lifespan_handler(scope, receive, send)
            return

        if scope["type"] == "http":
            scope["request"] = Request(scope, receive, send)

        if self._asgi_app is None:
            self._asgi_app = self._create_app()
        await self._asgi_app(scope, receive, send)

    def cli(self) -> None:
        self.bootstrap()
        set_current_application(self)

    def bootstrap(self) -> None:
        pass

    def _create_app(self) -> ASGIApp:
        app = Router(routes=self.routes)
        self.middleware.top(ExceptionMiddleware, handlers={})
        self.middleware.top(ServerErrorMiddleware, debug=True)
        for mw in reversed(self.middleware):
            app = mw.wrap(app)
        return app


_current_app: contextvars.ContextVar[Kupala] = contextvars.ContextVar('_current_app')


def set_current_application(app: Kupala) -> None:
    _current_app.set(app)


def get_current_application() -> Kupala:
    return _current_app.get()
