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
    routes_config: typing.Callable[[Routes], None] | str | None = None

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
        routes_config: typing.Callable[[Routes], None] | str | None = None,
        commands: list[click.Command] = None,
        storages: dict[str, Storage] = None,
        renderer: TemplateRenderer = None,
    ) -> None:
        # base configuration
        self.secret_key = secret_key
        self.request_class = request_class or self.request_class or Request

        # routes config preflight
        self.routes_config = routes_config or self.routes_config

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
        self.di = Injector(self)

        set_current_application(self)

        # bind extensions to this app
        self._initialize()

        # configure extensions
        self.configure()

        # load routes
        self.apply_routes(self.routes)

        # ASGI app instance
        self._asgi_app: ASGIHandler | None = None

    def _initialize(self) -> None:
        for _, extension in inspect.getmembers(self, lambda x: hasattr(x, 'initialize')):
            extension.initialize(self)

    def configure(self) -> None:
        pass

    def apply_middleware(self, stack: MiddlewareStack) -> None:
        pass

    def apply_routes(self, routes: Routes) -> None:
        if self.routes_config:
            if callable(self.routes_config):
                self.routes_config(routes)
            else:
                routes.include(self.routes_config)

    def create_asgi_app(self) -> ASGIHandler:
        self.apply_middleware(self.middleware)
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
        if self._asgi_app is None:
            self._asgi_app = self.create_asgi_app()
        return self._asgi_app

    def render(self, template_name: str, context: dict[str, typing.Any] = None) -> str:
        return self.renderer.render(template_name, context or {})

    def cli(self) -> int:
        set_current_application(self)
        app = ConsoleApplication(self, self.commands)
        return app.run()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
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
