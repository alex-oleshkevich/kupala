from __future__ import annotations

import contextvars as cv
import logging
import traceback
import typing as t
from contextlib import AsyncExitStack
from starlette.middleware.errors import ServerErrorMiddleware
from starlette.routing import BaseRoute
from starlette.types import ASGIApp, Receive, Scope, Send

from kupala.config import Config
from kupala.container import Container, Resolver
from kupala.contracts import Invoker
from kupala.dotenv import DotEnv
from kupala.exceptions import ErrorHandler, ExceptionMiddleware
from kupala.middleware import MiddlewareStack
from kupala.providers import Provider
from kupala.requests import Request
from kupala.routing import Router, Routes
from kupala.templating import ContextProcessor, TemplateRenderer

_SERVICE = t.TypeVar('_SERVICE')


class Kupala:
    def __init__(
        self,
        debug: bool = None,
        config: t.Mapping = None,
        environment: str = None,
        env_prefix: str = '',
        dotenv: t.List[str] = None,
        routes: t.Union[Routes, t.List[BaseRoute]] = None,
        renderer: TemplateRenderer = None,
        context_processors: t.List[ContextProcessor] = None,
        error_handlers: t.Dict[t.Union[t.Type[Exception], int], ErrorHandler] = None,
        providers: t.Iterable[Provider] = None,
    ) -> None:
        self.lifespan: t.List[t.Callable[[Kupala], t.AsyncContextManager]] = []
        self.routes = Routes(list(routes) if routes else [])
        self.config = Config(config)
        self.dotenv = DotEnv(dotenv or ['.env.defaults', '.env'], env_prefix)
        self.env = self.dotenv.str('APP_ENV', 'production') if environment is None else environment
        self.debug = self.dotenv.bool('APP_DEBUG', False) if debug is None else debug
        self.middleware = MiddlewareStack()
        self.providers = providers or []
        self.renderer: t.Optional[TemplateRenderer] = renderer
        self.context_processors: t.List[ContextProcessor] = context_processors or []
        self.error_handlers = error_handlers or {}
        self.services = Container()

        self._asgi_app: t.Optional[ASGIApp] = None
        self._router: t.Optional[Router] = None
        self._request_container: cv.ContextVar[Container] = cv.ContextVar('_request_container', default=self.services)
        self._request: cv.ContextVar[t.Optional[Request]] = cv.ContextVar('_current_request')

        self.services.bind(Container, self.services)
        self.services.bind(Resolver, self.services)
        self.services.bind(Invoker, self.services)

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

        request_container = Container(parent=self.services)
        scope['resolver'] = request_container

        if scope["type"] == "lifespan":
            await self.lifespan_handler(scope, receive, send)
            return

        if scope["type"] == "http":
            request = Request(scope, receive, send)
            request_container.bind(Request, request)
            scope["request"] = request
            self._request.set(request)

        if self._asgi_app is None:
            self._asgi_app = self._create_app()

        self._request_container.set(request_container)
        with request_container.change_context():
            await self._asgi_app(scope, receive, send)

    def cli(self) -> None:
        set_current_application(self)
        self.bootstrap()

    def bootstrap(self) -> None:
        for provider in self.providers:
            provider.register(self.services)
        for provider in self.providers:
            provider.bootstrap(self.services)

    def _create_app(self) -> ASGIApp:
        app: ASGIApp = Router(routes=self.routes)
        self._router = t.cast(Router, app)
        self.middleware.top(ExceptionMiddleware, handlers=self.error_handlers)
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

    def invoke(self, fn_or_class: t.Union[t.Callable, t.Type], extra_kwargs: t.Dict[str, t.Any] = None) -> t.Any:
        """Resolve callable dependencies and call it passing dependencies to callable arguments.
        If `fn_or_class` is a type then it will be instantiated.

        Use `extra_kwargs` to provide dependency hints to the injector."""
        return self._request_container.get().invoke(fn_or_class, extra_kwargs=extra_kwargs)

    def resolve(self, key: t.Type[_SERVICE]) -> _SERVICE:
        """Resolve a service from the current container."""
        return self._request_container.get().resolve(key)


_current_app: cv.ContextVar[Kupala] = cv.ContextVar('_current_app')


def set_current_application(app: Kupala) -> None:
    _current_app.set(app)


def get_current_application() -> Kupala:
    return _current_app.get()
