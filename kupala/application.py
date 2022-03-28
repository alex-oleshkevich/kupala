from __future__ import annotations

import click
import contextvars as cv
import jinja2
import logging
import os
import secrets
import traceback
import typing
from contextlib import AsyncExitStack
from starlette.datastructures import State
from starlette.routing import BaseRoute
from starlette.types import ASGIApp, Receive, Scope, Send

from kupala import json
from kupala.cache import CacheManager
from kupala.console.application import ConsoleApplication
from kupala.contracts import TemplateRenderer
from kupala.di import Injector
from kupala.exceptions import ShutdownError, StartupError
from kupala.http.asgi import ASGIHandler
from kupala.http.context_processors import standard_processors
from kupala.http.middleware import Middleware, MiddlewareStack
from kupala.http.middleware.errors import ServerErrorMiddleware
from kupala.http.middleware.exception import ErrorHandler
from kupala.http.protocols import ContextProcessor
from kupala.http.requests import Request
from kupala.http.responses import Response
from kupala.http.routing import Router, Routes
from kupala.i18n.protocols import Translator
from kupala.mails import MailerManager
from kupala.storages.storages import StorageManager
from kupala.templating import JinjaRenderer


def _setup_default_jinja_env(
    app: Kupala,
    template_dirs: str | os.PathLike | list[str | os.PathLike],
) -> jinja2.Environment:
    template_dirs = [template_dirs] if isinstance(template_dirs, (str, os.PathLike)) else template_dirs
    loader = jinja2.ChoiceLoader(
        [
            jinja2.PackageLoader('kupala'),
            jinja2.FileSystemLoader(template_dirs),
        ]
    )
    env = jinja2.Environment(loader=loader, extensions=['jinja2.ext.debug'])
    env.globals.update(
        {
            'static': app.static_url,
        }
    )
    env.policies.update(
        {
            'json.dumps_function': json.dumps,
            'json.dumps_kwargs': {"ensure_ascii": False, "sort_keys": True},
        }
    )
    return env


class App:
    state: State

    def __init__(
        self,
        secret_key: str,
        routes: Routes,
        debug: bool = False,
        renderer: TemplateRenderer | None = None,
        commands: list[click.Command] | None = None,
        context_processors: list[ContextProcessor] | None = None,
        middleware: list[Middleware] | MiddlewareStack | None = None,
        lifespan_handlers: list[typing.Callable[[App], typing.AsyncContextManager[None]]] = None,
    ) -> None:
        self.secret_key = secret_key
        self.debug = debug
        self.state = State()
        self.state.storages = StorageManager()
        self.state.mailers = MailerManager()
        self.state.caches = CacheManager()
        self.state.renderer = renderer

        self._router = Router(routes)
        self._renderer = renderer
        self._commands = commands or []
        self._middleware = MiddlewareStack(list(middleware or []))
        self._lifespan_handlers = lifespan_handlers or []
        self._asgi_handler = self._build_middleware()
        self.context_processors = context_processors or []
        self.context_processors.append(standard_processors)
        self.di = Injector(self)

    @property
    def storages(self) -> StorageManager:
        return self.state.storages

    @property
    def mailers(self) -> MailerManager:
        return self.state.mailers

    @property
    def caches(self) -> CacheManager:
        return self.state.caches

    @property
    def translator(self) -> Translator:
        assert hasattr(self.state, 'translator'), 'Translations are not enabled.'
        return self.state.translator

    async def lifespan_handler(self, scope: Scope, receive: Receive, send: Send) -> None:
        started = False
        try:
            await receive()
            async with AsyncExitStack() as stack:
                for hook in self._lifespan_handlers:
                    await stack.enter_async_context(hook(self))
                await send({'type': 'lifespan.startup.complete'})
                started = True
                await receive()
        except BaseException as ex:
            text = traceback.format_exc()
            if started:
                await send({'type': 'lifespan.shutdown.failed', 'message': text})
                raise ShutdownError(text) from ex
            else:
                await send({'type': 'lifespan.startup.failed', 'message': text})
                raise StartupError(text) from ex
        else:
            await send({'type': 'lifespan.shutdown.complete'})

    def cli(self) -> int:
        """Run console application."""
        set_current_application(self)
        return ConsoleApplication(self, self._commands).run()

    def render(self, template_name: str, context: dict[str, typing.Any] = None) -> str:
        """Render template."""
        assert self._renderer, 'Configure application with renderer instance to support template rendering.'
        return self._renderer.render(template_name, context or {})

    def url_for(self, name: str, **path_params: str) -> str:
        """
        Generate URL by name.

        This method is useful when you want to reverse the URL in non-ASGI mode
        like CLI. Otherwise, prefer using Request.url_for as it generates full
        URL incl. host and scheme.
        """
        return self._router.url_path_for(name, **path_params)

    def static_url(self, path: str, path_name: str = 'static') -> str:
        return self.url_for(path_name, path=path)

    def _build_middleware(self) -> ASGIApp:
        self._middleware.top(ServerErrorMiddleware, debug=self.debug)
        app: ASGIApp = self._router
        for mw in reversed(self._middleware):
            app = mw.wrap(app)
        return app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        assert scope['type'] in {'http', 'websocket', 'lifespan'}
        if scope['type'] == 'lifespan':
            await self.lifespan_handler(scope, receive, send)
            return

        scope['app'] = self
        set_current_application(self)
        await self._asgi_handler(scope, receive, send)


class Kupala:
    state: State

    def __init__(
        self,
        *,
        secret_key: str | None = None,
        debug: bool = False,
        environment: str = 'production',
        middleware: list[Middleware] | None = None,
        routes: list[BaseRoute] | Routes | None = None,
        request_class: typing.Type[Request] = Request,
        error_handlers: dict[typing.Type[Exception] | int, typing.Optional[ErrorHandler]] | None = None,
        lifespan_handlers: list[typing.Callable[[Kupala], typing.AsyncContextManager[None]]] = None,
        exception_handler: typing.Callable[[Request, Exception], Response] | None = None,
        commands: list[click.Command] | None = None,
        context_processors: list[ContextProcessor] | None = None,
        renderer: TemplateRenderer | None = None,
        template_dir: str | os.PathLike | list[str | os.PathLike] = 'templates',
        static_dir: str | os.PathLike | None = None,
    ) -> None:
        # base configuration
        self.secret_key = secret_key
        if self.secret_key is None:
            self.secret_key = secrets.token_hex(128)
            logging.warning(
                'Secret key is not defined. Will generate temporary secret. '
                'This value will be reset after application restart.'
            )

        self.debug = debug
        self.environment = environment
        self.request_class = request_class
        self.commands = commands or []
        self.jinja_env = _setup_default_jinja_env(self, template_dirs=template_dir)

        self.context_processors = context_processors or []
        self.context_processors.append(standard_processors)

        # default services
        self.state = State()
        self.state.storages = StorageManager()
        self.state.mailers = MailerManager()
        self.state.caches = CacheManager()
        self.state.renderer = renderer or JinjaRenderer(self.jinja_env)

        self.error_handlers = error_handlers or {}
        self.lifespan = lifespan_handlers or []
        self.exception_handler = exception_handler
        self.middleware = MiddlewareStack(middleware)
        self.routes = Routes(routes or [])

        self.di = Injector(self)  # type: ignore

        # ASGI app instance
        self._asgi_app: ASGIHandler | None = None

        if static_dir:
            self.storages.add_local('static', static_dir)
            self.routes.files('/static', storage='static', name='static')

    @property
    def storages(self) -> StorageManager:
        return self.state.storages

    @property
    def mailers(self) -> MailerManager:
        return self.state.mailers

    @property
    def caches(self) -> CacheManager:
        return self.state.caches

    @property
    def translator(self) -> Translator:
        assert hasattr(self.state, 'translator'), 'Translations are not enabled.'
        return self.state.translator

    def create_asgi_app(self) -> ASGIHandler:
        return ASGIHandler(
            debug=self.debug,
            routes=self.routes,
            middleware=self.middleware,
            error_handlers=self.error_handlers,
            exception_handler=self.exception_handler,
        )

    def get_asgi_app(self) -> ASGIHandler:
        """
        Creates ASGI handler.

        Subsequent calls will return cached instance.
        """
        if self._asgi_app is None:
            self._asgi_app = self.create_asgi_app()
        return self._asgi_app

    def render(self, template_name: str, context: dict[str, typing.Any] = None) -> str:
        """Render template."""
        return self.state.renderer.render(template_name, context or {})

    def url_for(self, name: str, **path_params: str) -> str:
        """
        Generate URL by name.

        This method is useful when you want to reverse the URL in non-ASGI mode
        like CLI. Otherwise, prefer using Request.url_for as it generates full
        URL incl. host and scheme.
        """
        return self.get_asgi_app().router.url_path_for(name, **path_params)

    def static_url(self, path: str, path_name: str = 'static') -> str:
        return self.url_for(path_name, path=path)

    def cli(self) -> int:
        """Run console application."""
        set_current_application(self)  # type: ignore
        return ConsoleApplication(self, self.commands).run()  # type: ignore

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        assert scope['type'] in {'http', 'websocket', 'lifespan'}

        if scope['type'] == 'lifespan':
            # reset inner ASGI app because underlying routes stack may have been changed between
            # app instantiation and invocation of this method.
            # This may happen when you call app.url_for() or similar methods which instantiate ASGI application
            # to complete
            # TODO: may be this is a bad idea
            self._asgi_app = None
            await self.lifespan_handler(scope, receive, send)
            return

        if self._asgi_app is None:
            self._asgi_app = self.get_asgi_app()

        assert self._asgi_app, 'ASGI application has not been initialized.'

        scope['app'] = self
        scope['state'] = {}
        if scope['type'] == 'http':
            scope['request'] = self.request_class(scope, receive)

        set_current_application(self)  # type: ignore
        await self._asgi_app(scope, receive, send)

    async def lifespan_handler(self, scope: Scope, receive: Receive, send: Send) -> None:
        started = False
        try:
            await receive()
            async with AsyncExitStack() as stack:
                for hook in self.lifespan:
                    await stack.enter_async_context(hook(self))
                await send({'type': 'lifespan.startup.complete'})
                started = True
                await receive()
        except BaseException as ex:
            text = traceback.format_exc()
            if started:
                await send({'type': 'lifespan.shutdown.failed', 'message': text})
                raise ShutdownError(text) from ex
            else:
                await send({'type': 'lifespan.startup.failed', 'message': text})
                raise StartupError(text) from ex
        else:
            await send({'type': 'lifespan.shutdown.complete'})

    def set_renderer(self, renderer: TemplateRenderer) -> None:
        self.state.renderer = renderer


_current_app: cv.ContextVar[App] = cv.ContextVar('_current_app')


def set_current_application(app: App) -> None:
    _current_app.set(app)


def get_current_application() -> App:
    return _current_app.get()
