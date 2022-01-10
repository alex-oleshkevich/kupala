from __future__ import annotations

import click
import contextvars as cv
import inspect
import logging
import os
import secrets
import typing
from starlette.datastructures import State
from starlette.routing import BaseRoute
from starlette.types import Receive, Scope, Send

from kupala.asgi import ASGIHandler
from kupala.config import Config
from kupala.console.application import ConsoleApplication
from kupala.contracts import TemplateRenderer
from kupala.di import Injector
from kupala.dotenv import DotEnv
from kupala.extensions import (
    AuthenticationExtension,
    ConsoleExtension,
    JinjaExtension,
    MailExtension,
    PasswordsExtension,
    RendererExtension,
    SignerExtension,
    StaticFiles,
    StoragesExtension,
    URLExtension,
)
from kupala.middleware import Middleware, MiddlewareStack
from kupala.middleware.exception import ErrorHandler
from kupala.requests import Request
from kupala.responses import Response
from kupala.routing import Routes
from kupala.storages.storages import Storage
from kupala.utils import resolve_path


class Kupala:
    request_class = Request

    def __init__(
        self,
        *,
        secret_key: str = None,
        debug: bool = None,
        env_file: str = '.env',
        middleware: list[Middleware] = None,
        routes: list[BaseRoute] | Routes | None = None,
        request_class: typing.Type[Request] | None = None,
        error_handlers: dict[typing.Type[Exception] | int, typing.Optional[ErrorHandler]] = None,
        lifespan_handlers: list[typing.Callable[[Kupala], typing.AsyncContextManager[None]]] = None,
        exception_handler: typing.Callable[[Request, Exception], Response] | None = None,
        template_dir: str | list[str] = 'templates',
        commands: list[click.Command] = None,
        storages: dict[str, Storage] = None,
        renderer: TemplateRenderer = None,
    ) -> None:
        # base configuration
        self.secret_key = secret_key
        self.request_class = request_class or self.request_class or Request

        # read environment and set default variables
        self.environ = DotEnv([env_file])
        self.secret_key = secret_key or self.environ.get('SECRET_KEY', default=None, check_file=True)
        if self.secret_key is None:
            self.secret_key = secrets.token_hex(128)
            logging.warning(
                'Secret key is not defined. Will generate temporary secret. '
                'This value will be reset after application restart.'
            )

        self.debug = debug if debug is not None else self.environ.bool('APP_DEBUG', False)
        self.environment = self.environ.get('APP_ENV', 'production')

        # ASGI related
        self.error_handlers = error_handlers or {}
        self.lifespan = lifespan_handlers or []
        self.exception_handler = exception_handler
        self.middleware = MiddlewareStack(middleware)
        self.routes = Routes(routes or [])

        # assign core components
        template_dirs = [template_dir] if isinstance(template_dir, (str, os.PathLike)) else template_dir or []
        self.jinja = JinjaExtension(template_dirs=[resolve_path(directory) for directory in template_dirs])
        self.config = Config()
        self.state = State()
        self.passwords = PasswordsExtension()
        self.mail = MailExtension()
        self.auth = AuthenticationExtension(self)
        self.storages = StoragesExtension(storages)
        self.commands = ConsoleExtension(commands)
        self.signer = SignerExtension(self.secret_key)
        self.renderer = RendererExtension(renderer or self.jinja.renderer)
        self.staticfiles = StaticFiles(self)
        self.urls = URLExtension(self)
        self.di = Injector(self)

        set_current_application(self)

        # bind extensions to this app
        self._initialize()

        # ASGI app instance
        self._asgi_app: ASGIHandler | None = None

    def _initialize(self) -> None:
        for _, extension in inspect.getmembers(self, lambda x: hasattr(x, 'initialize')):
            extension.initialize(self)

    def create_asgi_app(self) -> ASGIHandler:
        return ASGIHandler(
            app=self,
            debug=self.debug,
            routes=self.routes,
            middleware=self.middleware,
            error_handlers=self.error_handlers,
            lifespan_handlers=self.lifespan,
            exception_handler=self.exception_handler,
            request_class=self.request_class,
        )

    def get_asgi_app(self) -> ASGIHandler:
        """Creates ASGI handler. Subsequent calls will return cached instance."""
        if self._asgi_app is None:
            self._asgi_app = self.create_asgi_app()
        return self._asgi_app

    def render(self, template_name: str, context: dict[str, typing.Any] = None) -> str:
        """Render template."""
        return self.renderer.render(template_name, context or {})

    def url_for(self, name: str, **path_params: str) -> str:
        """Generate URL by name. This method is useful when you want to reverse the URL in non-ASGI mode like CLI.
        Otherwise, prefer using Request.url_for as it generates full URL incl. host and scheme."""
        return self.urls.url_for(name, **path_params)

    def cli(self) -> int:
        """Run console application."""
        set_current_application(self)
        app = ConsoleApplication(self, self.commands)
        return app.run()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope['type'] == 'lifespan':
            # reset inner ASGI app because underlying routes stack may have been changed between
            # app instantiation and invocation of this method.
            # This may happen when you call app.url_for() or similar methods which instantiate ASGI application
            # to complete
            # TODO: may be this is a bad idea
            self._asgi_app = None

        if self._asgi_app is None:
            try:
                self._asgi_app = self.get_asgi_app()
            except Exception as ex:
                logging.exception(ex)
                await send({'type': 'lifespan.startup.failed', 'message': str(ex)})
                raise ex

        assert self._asgi_app, 'ASGI application has not been initialized.'
        await self._asgi_app(scope, receive, send)


_current_app: cv.ContextVar[Kupala] = cv.ContextVar('_current_app')


def set_current_application(app: Kupala) -> None:
    _current_app.set(app)


def get_current_application() -> Kupala:
    return _current_app.get()
