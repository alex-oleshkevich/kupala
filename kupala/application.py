from __future__ import annotations

import click
import contextvars as cv
import jinja2
import jinja2.ext
import logging
import os
import secrets
import traceback
import typing
from babel.numbers import format_decimal
from contextlib import AsyncExitStack
from imia import BaseAuthenticator, LoginManager, UserProvider
from starlette.datastructures import State
from starlette.routing import BaseRoute
from starlette.types import Receive, Scope, Send

from kupala import json
from kupala.asgi import ASGIHandler
from kupala.console.application import ConsoleApplication
from kupala.contracts import PasswordHasher, TemplateRenderer
from kupala.di import Injector
from kupala.exceptions import ShutdownError, StartupError
from kupala.i18n.formatters import (
    format_currency,
    format_date,
    format_datetime,
    format_number,
    format_percent,
    format_scientific,
    format_time,
    format_timedelta,
)
from kupala.mails import MailerManager
from kupala.middleware import Middleware, MiddlewareStack
from kupala.middleware.exception import ErrorHandler
from kupala.requests import Request
from kupala.responses import Response
from kupala.routing import Routes
from kupala.storages.storages import Storage, StorageManager
from kupala.templating import JinjaRenderer
from kupala.utils import import_string


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
        error_handlers: dict[typing.Type[Exception] | int, typing.Optional[ErrorHandler]] = None,
        lifespan_handlers: list[typing.Callable[[Kupala], typing.AsyncContextManager[None]]] = None,
        exception_handler: typing.Callable[[Request, Exception], Response] | None = None,
        template_dir: str | os.PathLike | list[str | os.PathLike] = 'templates',
        commands: list[click.Command] | None = None,
        storages: dict[str, Storage] | None = None,
        renderer: TemplateRenderer | None = None,
    ) -> None:
        # base configuration
        self.debug = debug
        self.environment = environment
        self.request_class = request_class
        self.commands = commands or []
        self.state = State()

        self.secret_key = secret_key
        if self.secret_key is None:
            self.secret_key = secrets.token_hex(128)
            logging.warning(
                'Secret key is not defined. Will generate temporary secret. '
                'This value will be reset after application restart.'
            )

        # ASGI related
        self.error_handlers = error_handlers or {}
        self.lifespan = lifespan_handlers or []
        self.exception_handler = exception_handler
        self.middleware = MiddlewareStack(middleware)
        self.routes = Routes(routes or [])

        # templating
        if renderer:
            self.use_renderer(renderer)
        else:
            self.use_jinja_renderer(template_dirs=template_dir)

        # assign core components
        self.di = Injector(self)
        self.mail = MailerManager()
        self.storages = StorageManager(storages)

        # ASGI app instance
        self._asgi_app: ASGIHandler | None = None

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
        self.storages.add_local(name, directory)
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

    def use_password_hasher(
        self,
        hasher: typing.Literal['pbkdf2_sha256', 'pbkdf2_sha512', 'argon2', 'bcrypt', 'des_crypt'] | PasswordHasher,
    ) -> None:
        if isinstance(hasher, str):
            imports = {
                'pbkdf2_sha256': 'passlib.handlers.pbkdf2:pbkdf2_sha256',
                'pbkdf2_sha512': 'passlib.handlers.pbkdf2:pbkdf2_sha512',
                'argon2': 'passlib.handlers.argon2:argon2',
                'bcrypt': 'passlib.handlers.bcrypt:bcrypt',
                'des_crypt': 'passlib.handlers.des_crypt:des_crypt',
            }
            hasher = typing.cast(PasswordHasher, import_string(imports[hasher]))
        self.state.password_hasher = hasher
        self.di.prefer_for(PasswordHasher, lambda app: app.state.password_hasher)

    def use_authentication(
        self,
        user_provider: UserProvider,
        user_model: typing.Type[typing.Any] | None = None,
        authenticators: list[BaseAuthenticator] | None = None,
    ) -> None:
        self.state.login_manager = LoginManager(
            secret_key=self.secret_key,
            user_provider=user_provider,
            password_verifier=self.state.password_hasher,
        )
        self.di.make_injectable(LoginManager, from_app_factory=lambda app: app.state.login_manager)

    def use_renderer(self, renderer: TemplateRenderer) -> None:
        self.state.renderer = renderer

    def use_jinja_renderer(
        self,
        template_dirs: str | os.PathLike | list[str | os.PathLike],
        tests: dict[str, typing.Callable] = None,
        filters: dict[str, typing.Callable] = None,
        globals: dict[str, typing.Any] = None,
        policies: dict[str, typing.Any] = None,
        extensions: list[str | typing.Type[jinja2.ext.Extension]] = None,
        env: jinja2.Environment = None,
        loader: jinja2.BaseLoader = None,
    ) -> None:
        template_dirs = [template_dirs] if isinstance(template_dirs, (str, os.PathLike)) else template_dirs
        loader = loader or jinja2.loaders.FileSystemLoader(searchpath=template_dirs)
        env = env or jinja2.Environment(loader=loader, extensions=extensions or [])
        env.tests.update(tests or {})
        env.globals.update(globals or {})
        env.filters.update(filters or {})
        env.policies.update(policies or {})

        env.filters.update(
            {
                'datetimeformat': format_datetime,
                'dateformat': format_date,
                'timeformat': format_time,
                'timedeltaformat': format_timedelta,
                'numberformat': format_number,
                'decimalformat': format_decimal,
                'currencyformat': format_currency,
                'percentformat': format_percent,
                'scientificformat': format_scientific,
            }
        )
        env.globals.update(
            {
                'static': self.static_url,
                '_': lambda x: x,
            }
        )

        if 'json.dumps_function' not in env.policies:
            env.policies['json.dumps_function'] = json.dumps

        if "json.dumps_kwargs" not in env.policies:
            env.policies["json.dumps_kwargs"] = {"ensure_ascii": False, "sort_keys": True}

        self.state.jinja_env = env
        self.use_renderer(JinjaRenderer(env))


_current_app: cv.ContextVar[Kupala] = cv.ContextVar('_current_app')


def set_current_application(app: Kupala) -> None:
    _current_app.set(app)


def get_current_application() -> Kupala:
    return _current_app.get()
