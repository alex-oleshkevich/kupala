from __future__ import annotations

import contextvars as cv
import jinja2
import logging
import secrets
import typing
from starlette.datastructures import State
from starlette.routing import BaseRoute
from starlette.types import ASGIApp

from kupala.app.asgi import ASGIHandler
from kupala.app.components import Passwords, Renderer
from kupala.config import Config
from kupala.dotenv import DotEnv
from kupala.ext.jinja import JinjaRenderer
from kupala.middleware import Middleware, MiddlewareStack
from kupala.middleware.exception import ErrorHandler
from kupala.requests import Request
from kupala.responses import Response
from kupala.routing import Routes
from kupala.utils import resolve_path


class BaseApp:
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
        lifespan_handlers: list[typing.Callable[[BaseApp], typing.AsyncContextManager]] = None,
        exception_handler: typing.Callable[[Request, Exception], Response] | None = None,
        template_dir: str | list[str] = 'templates',
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

        self.jinja_env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(
                searchpath=[resolve_path(template_path) for template_path in self.template_dirs]
            )
        )
        self.jinja_env.policies["json.dumps_kwargs"] = {"ensure_ascii": False, "sort_keys": True}
        self.renderer = Renderer(JinjaRenderer(self.jinja_env))

        set_current_application(self)
        self.bootstrap()

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


_current_app: cv.ContextVar[BaseApp] = cv.ContextVar('_current_app')


def set_current_application(app: BaseApp) -> None:
    _current_app.set(app)


def get_current_application() -> BaseApp:
    return _current_app.get()
