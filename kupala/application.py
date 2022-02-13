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
from starlette.types import Receive, Scope, Send

from kupala import json
from kupala.asgi import ASGIHandler
from kupala.cache import CacheManager
from kupala.console.application import ConsoleApplication
from kupala.contracts import TemplateRenderer, Translator
from kupala.di import Injector
from kupala.exceptions import ShutdownError, StartupError
from kupala.mails import MailerManager
from kupala.middleware import Middleware, MiddlewareStack
from kupala.middleware.exception import ErrorHandler
from kupala.requests import Request
from kupala.responses import Response
from kupala.routing import Routes
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
    env = jinja2.Environment(loader=loader, extensions=['jinja2.ext.with_', 'jinja2.ext.debug'])
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


class Kupala:
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

        # default services
        self.state = State()
        self.state.storages = StorageManager()
        self.state.mailers = MailerManager()
        self.state.caches = CacheManager()
        self.state.renderer = renderer or JinjaRenderer(self.jinja_env)

        # ASGI related
        self.error_handlers = error_handlers or {}
        self.lifespan = lifespan_handlers or []
        self.exception_handler = exception_handler
        self.middleware = MiddlewareStack(middleware)
        self.routes = Routes(routes or [])

        self.di = Injector(self)

        # ASGI app instance
        self._asgi_app: ASGIHandler | None = None

        if static_dir:
            self.serve_static_files(static_dir)

    @property
    def storages(self) -> StorageManager:
        return self.state.storages

    @property
    def mailers(self) -> MailerManager:
        return self.state.mailers

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

    def serve_static_files(self, directory: str | os.PathLike, url_path: str = '/static', name: str = 'static') -> None:
        """
        Serve static files from local directory. This will create a file route
        and local storage both named after "name" argument.

        :param directory: full path to the local directory path
        :param url_path: URL path to use in route
        :param name: route and storage name
        """
        self.state.storages.add_local(name, directory)
        self.routes.files(url_path, storage=name, name=name, inline=False)

    def cli(self) -> int:
        """Run console application."""
        set_current_application(self)
        return ConsoleApplication(self, self.commands).run()

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

        set_current_application(self)
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


_current_app: cv.ContextVar[Kupala] = cv.ContextVar('_current_app')


def set_current_application(app: Kupala) -> None:
    _current_app.set(app)


def get_current_application() -> Kupala:
    return _current_app.get()
