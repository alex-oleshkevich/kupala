from __future__ import annotations

import click
import contextvars as cv
import jinja2
import logging
import secrets
import typing
from starlette.datastructures import State
from starlette.routing import BaseRoute
from starlette.types import ASGIApp, Receive, Scope, Send

from kupala.asgi import ASGIHandler
from kupala.config import Config
from kupala.console.application import ConsoleApplication
from kupala.contracts import TemplateRenderer
from kupala.dotenv import DotEnv
from kupala.extensions import Authentication, Mail, Passwords, Renderer, Storages
from kupala.middleware import Middleware, MiddlewareStack
from kupala.middleware.exception import ErrorHandler
from kupala.requests import Request
from kupala.responses import Response
from kupala.routing import Routes
from kupala.storages.storages import Storage
from kupala.templating import JinjaRenderer
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

        self.template_dirs = [template_dir] if isinstance(template_dir, str) else template_dir or []

        # assign core components
        self.config = Config()
        self.state = State()
        self.passwords = Passwords()
        self.mail = Mail()
        self.auth = Authentication(self)
        self.storages = Storages(storages)
        self.commands = commands or []

        self.jinja_env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(
                searchpath=[resolve_path(template_path) for template_path in self.template_dirs]
            )
        )
        self.jinja_env.policies["json.dumps_kwargs"] = {"ensure_ascii": False, "sort_keys": True}
        self.renderer = Renderer(renderer or JinjaRenderer(self.jinja_env))

        set_current_application(self)
        self.bootstrap()

        # ASGI app instance
        self._asgi_app: ASGIApp | None = None

    def bootstrap(self) -> None:
        pass

    def apply_middleware(self) -> None:
        pass

    def create_asgi_app(self) -> ASGIApp:
        self.apply_middleware()
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

    def cli(self) -> int:
        set_current_application(self)
        app = ConsoleApplication(self, self.commands)
        return app.run()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if self._asgi_app is None:
            self._asgi_app = self.create_asgi_app()
        await self._asgi_app(scope, receive, send)


_current_app: cv.ContextVar[Kupala] = cv.ContextVar('_current_app')


def set_current_application(app: Kupala) -> None:
    _current_app.set(app)


def get_current_application() -> Kupala:
    return _current_app.get()
