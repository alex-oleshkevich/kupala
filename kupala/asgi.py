from __future__ import annotations

import logging
import traceback
import typing
from contextlib import AsyncExitStack
from starlette.types import ASGIApp, Receive, Scope, Send

from kupala.middleware import MiddlewareStack
from kupala.middleware.errors import ServerErrorMiddleware
from kupala.middleware.exception import ErrorHandler, ExceptionMiddleware
from kupala.requests import Request
from kupala.responses import Response
from kupala.routing import Router, Routes

if typing.TYPE_CHECKING:  # pragma: nocover
    from kupala.application import Kupala


class ASGIHandler:
    def __init__(
        self,
        app: Kupala,
        *,
        debug: bool,
        routes: Routes,
        middleware: MiddlewareStack,
        error_handlers: dict[typing.Type[Exception] | int, typing.Optional[ErrorHandler]],
        lifespan_handlers: list[typing.Callable[[Kupala], typing.AsyncContextManager]],
        exception_handler: typing.Callable[[Request, Exception], Response] | None,
        request_class: typing.Type[Request] = None,
    ) -> None:
        self.app = app
        self.debug = debug
        self.middleware = middleware
        self.routes = Routes(routes or [])
        self.error_handlers = error_handlers
        self.exception_handler = exception_handler
        self.lifespan_handlers = lifespan_handlers
        self.request_class = request_class or Request

        middleware.use(ExceptionMiddleware, handlers=error_handlers)
        middleware.top(ServerErrorMiddleware, debug=debug, handler=self.exception_handler)
        self.router = Router(routes=routes)
        self.asgi_app: ASGIApp = self.router
        for mw in reversed(middleware):
            self.asgi_app = mw.wrap(self.asgi_app)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        assert scope['type'] in {'http', 'websocket', 'lifespan'}
        if scope['type'] == 'lifespan':
            await self.lifespan_handler(scope, receive, send)
            return

        scope['app'] = self.app
        scope['state'] = {}
        if scope['type'] == 'http':
            request = self.request_class(scope, receive, send)
            scope['request'] = request
        await self.asgi_app(scope, receive, send)

    async def lifespan_handler(self, scope: Scope, receive: Receive, send: Send) -> None:
        started = False
        try:
            await receive()
            async with AsyncExitStack() as stack:
                for hook in self.lifespan_handlers:
                    await stack.enter_async_context(hook(self.app))
                await send({'type': 'lifespan.startup.complete'})
                started = True
                await receive()
        except BaseException as ex:
            logging.exception(ex)
            logging.error(f'Application failed to boot: {ex}.')
            text = traceback.format_exc()
            if started:
                await send({'type': 'lifespan.shutdown.failed', 'message': text})
            else:
                await send({'type': 'lifespan.startup.failed', 'message': text})
        else:
            await send({'type': 'lifespan.shutdown.complete'})
