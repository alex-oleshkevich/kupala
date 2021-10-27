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
from kupala.templating import ContextProcessor, TemplateRenderer


class Kupala:
    def __init__(
        self,
        debug: bool = None,
        config: t.Mapping = None,
        env_prefix: str = '',
        dotenv: t.List[str] = None,
        routes: t.Union[Routes, t.List[BaseRoute]] = None,
        renderer: TemplateRenderer = None,
        context_processors: t.List[ContextProcessor] = None,
    ) -> None:
        self.lifespan: t.List[t.Callable[[Kupala], t.AsyncContextManager]] = []
        self._asgi_app: t.Optional[ASGIApp] = None
        self.routes = Routes(list(routes) if routes else [])
        self.config = Config(config, dotenv, prefix=env_prefix)
        self.dotenv = self.config.dotenv
        self.env = self.dotenv.str('APP_ENV', 'production')
        self.debug = self.dotenv.bool('APP_DEBUG', False) if debug is None else debug
        self.middleware = MiddlewareStack()
        self.renderer: t.Optional[TemplateRenderer] = renderer
        self.context_processors: t.List[ContextProcessor] = context_processors or []
        self._request: contextvars.ContextVar[t.Optional[Request]] = contextvars.ContextVar('_current_request')

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
            request = Request(scope, receive, send)
            scope["request"] = request
            self._request.set(request)

        if self._asgi_app is None:
            self._asgi_app = self._create_app()
        await self._asgi_app(scope, receive, send)

    def cli(self) -> None:
        set_current_application(self)
        self.bootstrap()

    def bootstrap(self) -> None:
        pass

    def _create_app(self) -> ASGIApp:
        app: ASGIApp = Router(routes=self.routes)
        self.middleware.top(ExceptionMiddleware, handlers={})
        self.middleware.top(ServerErrorMiddleware, debug=True)
        for mw in reversed(self.middleware):
            app = mw.wrap(app)
        return app

    def render(self, template_name: str, context: t.Mapping = None) -> str:
        assert self.renderer, 'A template renderer is not set on the application instance.'

        context = dict(context or {})
        try:
            # it will raise LookupError if self._request is unset
            request: Request = t.cast(Request, context.get('request') or self._request.get())
            context['request'] = self._request
            for processor in self.context_processors:
                context.update(processor(request))
        except LookupError:
            pass
        return self.renderer.render(template_name, context)


_current_app: contextvars.ContextVar[Kupala] = contextvars.ContextVar('_current_app')


def set_current_application(app: Kupala) -> None:
    _current_app.set(app)


def get_current_application() -> Kupala:
    return _current_app.get()
