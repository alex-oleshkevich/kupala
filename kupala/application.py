from __future__ import annotations

import contextvars as cv
import importlib
import jinja2
import os
import pathlib
import traceback
import typing
from contextlib import AsyncExitStack
from starception import StarceptionMiddleware
from starlette.datastructures import State
from starlette.exceptions import HTTPException
from starlette.routing import BaseRoute, Mount, Router
from starlette.staticfiles import StaticFiles
from starlette.types import ASGIApp, Receive, Scope, Send

from kupala import json
from kupala.dependencies import Injector
from kupala.exceptions import ShutdownError, StartupError
from kupala.http.middleware import Middleware, MiddlewareStack
from kupala.http.middleware.exception import (
    ErrorHandler,
    ExceptionMiddleware,
    default_http_error_handler,
    default_server_error_handler,
)
from kupala.templating import ContextProcessor, DynamicChoiceLoader

_T = typing.TypeVar("_T")

LifespanHandler = typing.Callable[["App"], typing.AsyncContextManager[None]]


class App:
    state: State

    def __init__(
        self,
        package_name: str,
        secret_key: str,
        *,
        debug: bool = False,
        routes: typing.Iterable[BaseRoute] | None = None,
        middleware: typing.Iterable[Middleware] | MiddlewareStack | None = None,
        error_handlers: dict[typing.Type[Exception] | int, ErrorHandler] | None = None,
        lifespan_handlers: typing.Iterable[LifespanHandler] = None,
        jinja_env: jinja2.Environment | None = None,
        static_dir: str | os.PathLike | typing.Literal["auto"] | None = "auto",
        template_dir: str | os.PathLike | list[str | os.PathLike] | typing.Literal["auto"] = "auto",
    ) -> None:
        self.secret_key = secret_key
        self.debug = debug
        self.package_name = package_name.split(".")[0]
        self.state = State()

        module = importlib.import_module(self.package_name)
        assert module.__file__, "Could not detect package directory path."
        self.base_dir = pathlib.Path(os.path.dirname(module.__file__))

        self._asgi_handler: ASGIApp | None = None
        self.routes = list(routes or [])
        self.middleware = MiddlewareStack(list(middleware or []))
        self.lifespan_handlers = list(lifespan_handlers or [])
        self.error_handlers: dict[int | typing.Type[Exception], ErrorHandler] = {
            Exception: default_server_error_handler,
            HTTPException: default_http_error_handler,
            **(error_handlers or {}),
        }
        self._router = Router(list(self.routes))
        self.dependencies = Injector()

        # region: templating setup
        _template_dirs: list[str | os.PathLike]
        if template_dir == "auto":
            _template_dirs = [self.base_dir / "templates"]
        elif isinstance(template_dir, (str, os.PathLike)):
            _template_dirs = [template_dir]
        else:
            _template_dirs = template_dir

        self._context_processors: list[ContextProcessor] = []
        self._jinja_loader = DynamicChoiceLoader(
            [
                jinja2.FileSystemLoader(_template_dirs),
                jinja2.PackageLoader("kupala"),
            ]
        )
        self.jinja_env = jinja_env or jinja2.Environment(loader=self._jinja_loader)
        self._setup_jinja()
        # endregion

        if static_dir == "auto":
            if (self.base_dir / "statics").exists():
                static_dir = self.base_dir / "statics"
            else:
                static_dir = None
        if static_dir:
            self.routes.append(Mount("/static", StaticFiles(directory=static_dir), name="static"))

    async def lifespan_handler(self, scope: Scope, receive: Receive, send: Send) -> None:
        started = False
        try:
            await receive()
            async with AsyncExitStack() as stack:
                for hook in self.lifespan_handlers:
                    await stack.enter_async_context(hook(self))
                await send({"type": "lifespan.startup.complete"})
                started = True
                await receive()
        except Exception as ex:
            text = traceback.format_exc()
            if started:
                await send({"type": "lifespan.shutdown.failed", "message": text})
                raise ShutdownError(text) from ex
            else:
                await send({"type": "lifespan.startup.failed", "message": text})
                raise StartupError(text) from ex
        else:
            await send({"type": "lifespan.shutdown.complete"})

    def url_for(self, name: str, **path_params: str) -> str:
        """
        Generate URL by name.

        This method is useful when you want to reverse the URL in non-ASGI mode like CLI. Otherwise, prefer using
        Request.url_for as it generates full URL incl. host and scheme.
        """
        return self._router.url_path_for(name, **path_params)

    def static_url(self, path: str, route_name: str = "static") -> str:
        """
        Generate URL to a static file.

        By default, a route with name 'static' used.
        """
        return self.url_for(route_name, path=path)

    def add_routes(self, *routes: BaseRoute) -> None:
        """Add one or more routes."""
        self.routes.extend(routes)

    def render(self, template_name: str, context: typing.Mapping[str, typing.Any] | None = None) -> str:
        """Render template to string."""
        template = self.jinja_env.get_template(template_name)
        return template.render(context or {})

    def add_middleware(self, middleware: typing.Type[ASGIApp], **options: typing.Any) -> None:
        """Register new ASGI middleware."""
        self.middleware.add(Middleware(middleware, **options))

    def add_error_handler(self, status_or_exc: int | typing.Type[Exception], handler: ErrorHandler) -> None:
        self.error_handlers[status_or_exc] = handler

    def add_lifespan_handlers(self, *handlers: LifespanHandler) -> None:
        self.lifespan_handlers.extend(handlers)

    def add_template_context_processors(self, *processors: ContextProcessor) -> None:
        """
        Add global template context processor.

        A context processor is a function that takes request and returns global template variables.
        """
        self._context_processors.extend(processors)

    def get_template_context_processors(self) -> list[ContextProcessor]:
        return self._context_processors

    def add_template_directories(self, *directories: str | os.PathLike) -> None:
        self._jinja_loader.add_loader(jinja2.FileSystemLoader(directories))

    def add_template_packages(self, *packages: str) -> None:
        for package in packages:
            self._jinja_loader.add_loader(jinja2.PackageLoader(package))

    def add_template_global(self, **globals: typing.Any) -> None:
        self.jinja_env.globals.update(globals)

    def add_template_extensions(self, *extensions: str) -> None:
        for extension in extensions:
            self.jinja_env.add_extension(extension)

    def add_template_tests(self, **tests: typing.Callable) -> None:
        self.jinja_env.tests.update(tests)

    def add_template_filters(self, **filters: typing.Any) -> None:
        self.jinja_env.filters.update(filters)

    def add_dependency(self, name: typing.Hashable, callback: typing.Callable, cached: bool = False) -> None:
        self.dependencies.add_dependency(name=name, callback=callback, cached=cached)

    def _build_middleware(self) -> ASGIApp:
        middleware = [
            Middleware(StarceptionMiddleware),
            *self.middleware,
            Middleware(ExceptionMiddleware, handlers=self.error_handlers),
        ]

        app: ASGIApp = Router(list(self.routes))
        self._router = app  # type: ignore[assignment]
        for mw in reversed(middleware):
            app = mw.wrap(app)
        return app

    def _setup_jinja(self) -> None:
        self.jinja_env.policies.update(
            {
                "json.dumps_function": json.dumps,
                "json.dumps_kwargs": {"ensure_ascii": False},
            }
        )
        self.jinja_env.globals.update(
            {
                "app": self,
                "url": self.url_for,
                "static": self.static_url,
            }
        )

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        assert scope["type"] in {"http", "websocket", "lifespan"}
        if scope["type"] == "lifespan":
            await self.lifespan_handler(scope, receive, send)
            return

        scope["app"] = self
        scope["state"] = {}
        set_current_application(self)

        try:
            # lazily create ASGI handler
            # this lets extensions alter application config without coding overhead
            await self._asgi_handler(scope, receive, send)  # type: ignore[misc]
        except TypeError:
            self._asgi_handler = self._build_middleware()
            await self._asgi_handler(scope, receive, send)


_current_app: cv.ContextVar[App] = cv.ContextVar("_current_app")


def set_current_application(app: App) -> None:
    _current_app.set(app)


def get_current_application() -> App:
    return _current_app.get()
