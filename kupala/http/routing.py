from __future__ import annotations

import functools
import inspect
import os
import typing
from starlette import routing
from starlette.routing import compile_path, get_name
from starlette.staticfiles import StaticFiles
from starlette.types import ASGIApp, Receive, Scope, Send

from kupala.http.dispatching import dispatch_endpoint
from kupala.http.middleware import Middleware
from kupala.http.responses import RedirectResponse
from kupala.storages.file_server import FileServer
from kupala.storages.storages import Storage
from kupala.utils import import_string


def apply_middleware(app: typing.Callable, middleware: typing.Sequence[Middleware]) -> ASGIApp:
    for mw in reversed(middleware):
        app = mw.wrap(app)
    return app


def request_response(func: typing.Callable) -> ASGIApp:
    """Takes a function or coroutine `func(request) -> response` and returns an
    ASGI application."""

    async def app(scope: Scope, receive: Receive, send: Send) -> None:
        response = await dispatch_endpoint(scope, receive, send, func)
        await response(scope, receive, send)

    return app


class Mount(routing.Mount):
    def __init__(
        self,
        path: str,
        app: ASGIApp = None,
        routes: typing.Sequence[routing.BaseRoute] = None,
        name: str = None,
        *,
        middleware: typing.Sequence[Middleware] = None,
    ) -> None:
        assert path == "" or path.startswith("/"), "Routed paths must start with '/'"
        assert app is not None or routes is not None, "Either 'app=...', or 'routes=' must be specified"
        self.path = path.rstrip("/")
        if app is not None:
            self.app: ASGIApp = app
            self._routes = getattr(app, 'routes', [])
        else:
            self.app = Router(routes=routes)
            self._routes = list(routes or [])
        self.name = name
        self.path_regex, self.path_format, self.param_convertors = compile_path(self.path + "/{path:path}")

        if middleware:
            self.app = apply_middleware(self.app, middleware)

    @property
    def routes(self) -> list[routing.BaseRoute]:
        return self._routes


class Host(routing.Host):
    def __init__(
        self, host: str, app: ASGIApp, name: str = None, *, middleware: typing.Sequence[Middleware] = None
    ) -> None:
        self.host = host
        self.app = app
        self.name = name
        self.host_regex, self.host_format, self.param_convertors = compile_path(host)
        self.middleware = middleware
        self._routes = getattr(app, 'routes', [])

        if middleware:
            self.app = apply_middleware(self.app, middleware)

    @property
    def routes(self) -> list[routing.BaseRoute]:
        return self._routes


class Router(routing.Router):
    pass


class Route(routing.Route):
    def __init__(
        self,
        path: str,
        endpoint: typing.Callable,
        *,
        name: str = None,
        include_in_schema: bool = True,
        methods: list[str] | None = None,
        middleware: typing.Sequence[Middleware] = None,
    ) -> None:
        assert path.startswith("/"), "Routed paths must start with '/'"
        self.path = path
        self.endpoint = endpoint
        self.name = get_name(endpoint) if name is None else name
        self.include_in_schema = include_in_schema

        methods = methods or getattr(endpoint, '__route_methods__', ['GET', 'HEAD'])
        middleware = middleware or getattr(endpoint, '__route_middleware__', [])

        endpoint_handler = endpoint
        while isinstance(endpoint_handler, functools.partial):
            endpoint_handler = endpoint_handler.func

        if inspect.isfunction(endpoint_handler) or inspect.ismethod(endpoint_handler):
            # Endpoint is function or method. Treat it as `func(request) -> response`.
            self.app = request_response(endpoint)
        else:
            # Endpoint is a class. Treat it as ASGI.
            self.app = endpoint

        if middleware:
            self.app = apply_middleware(typing.cast(typing.Callable, self.app), middleware)

        self.methods = {method.upper() for method in methods}
        if "GET" in self.methods:
            self.methods.add("HEAD")

        self.path_regex, self.path_format, self.param_convertors = compile_path(path)

    def __repr__(self) -> str:
        return f'<Route: path={self.path}, methods={self.methods}, name={self.name}>'


class WebSocketRoute(routing.WebSocketRoute):
    pass


class _RouteAdapter:
    _routes: Routes
    _base_app: ASGIApp | None

    def _create_base_asgi_app(self) -> ASGIApp:
        raise NotImplementedError()

    def __enter__(self) -> Routes:
        self._base_app = None  # force app recreate when routes change
        return self._routes

    def __exit__(self, *args: typing.Any) -> None:
        pass

    def __getattr__(self, item: str) -> typing.Any:
        try:
            return getattr(self._base_app, item)
        except AttributeError:
            self._base_app = self._create_base_asgi_app()
            return getattr(self._base_app, item)


class HostRoutes(_RouteAdapter):
    def __init__(
        self,
        host: str,
        routes: list[routing.BaseRoute] | Routes | None = None,
        name: str = None,
        middleware: typing.Sequence[Middleware] = None,
    ) -> None:
        self._host = host
        self._name = name
        self._routes = Routes(routes)
        self._middleware = middleware or []
        self._wrapped_app: ASGIApp | None = None
        self._base_app: Host | None = None

    def _create_base_asgi_app(self) -> ASGIApp:
        return Host(host=self._host, app=Router(routes=self._routes), name=self._name, middleware=self._middleware)


class GroupRoutes(_RouteAdapter):
    def __init__(
        self,
        prefix: str,
        routes: list[routing.BaseRoute] | Routes | None = None,
        name: str = None,
        middleware: typing.Sequence[Middleware] = None,
    ) -> None:
        self._name = name
        self._prefix = prefix
        self._routes = Routes(routes)
        self._middleware = middleware or []
        self._wrapped_app: ASGIApp | None = None
        self._base_app: Mount | None = None

    def _create_base_asgi_app(self) -> ASGIApp:
        return Mount(path=self._prefix, routes=self._routes, name=self._name, middleware=self._middleware)


class Routes(typing.Sequence[routing.BaseRoute]):
    def __init__(self, routes: typing.Iterable[routing.BaseRoute] = None) -> None:
        self._routes: list[routing.BaseRoute] = list(routes or [])

    def add(
        self,
        path: str,
        endpoint: typing.Callable,
        *,
        methods: list[str] = None,
        name: str = None,
        include_in_schema: bool = True,
        middleware: typing.Sequence[Middleware] = None,
    ) -> None:
        route = Route(
            path,
            endpoint,
            methods=methods,
            name=name,
            include_in_schema=include_in_schema,
            middleware=middleware,
        )
        self._routes.append(route)

    def websocket(self, path: str, endpoint: typing.Callable, *, name: str = None) -> None:
        self._routes.append(WebSocketRoute(path, endpoint, name=name))

    def mount(
        self, path: str, app: ASGIApp, *, name: str = None, middleware: typing.Sequence[Middleware] = None
    ) -> None:
        self._routes.append(Mount(path, app, name=name, middleware=middleware))

    def static(
        self,
        path: str,
        directory: str | os.PathLike[str] | None = None,
        *,
        packages: list[str | tuple[str, str]] | None = None,
        html: bool = False,
        check_dir: bool = True,
        name: str = 'static',
        middleware: typing.Sequence[Middleware] | None = None,
    ) -> None:
        """Serve static files from local directories."""
        app = StaticFiles(directory=directory, packages=packages, html=html, check_dir=check_dir)
        self.mount(path, app, name=name, middleware=middleware)

    def files(
        self,
        path: str,
        *,
        storage: Storage,
        name: str = None,
        middleware: typing.Sequence[Middleware] = None,
        inline: bool = False,
    ) -> None:
        """Serve file uploads from disk."""
        app = FileServer(storage=storage, as_attachment=inline)
        self._routes.append(Mount(path, app, name=name, middleware=middleware))

    def host(
        self,
        host: str,
        routes: Routes | list[routing.BaseRoute] | None = None,
        *,
        name: str = None,
        middleware: typing.Sequence[Middleware] = None,
    ) -> HostRoutes:
        app = HostRoutes(host, routes, name, middleware)
        self._routes.append(typing.cast(routing.Host, app))
        return app

    def group(
        self,
        prefix: str,
        routes: Routes | list[routing.BaseRoute] | None = None,
        *,
        name: str = None,
        middleware: typing.Sequence[Middleware] = None,
    ) -> GroupRoutes:
        app = GroupRoutes(prefix, routes, name, middleware)
        self._routes.append(typing.cast(routing.Mount, app))
        return app

    def redirect(self, path: str, destination: str, status_code: int = 307, headers: dict = None) -> None:
        self.mount(
            path,
            RedirectResponse(destination, status_code=status_code, headers=headers),
        )

    def include(
        self, iterable_or_module: typing.Iterable[routing.BaseRoute] | str, callback: str = 'configure'
    ) -> None:
        """Include routes."""
        IncludeRoutesCallback = typing.Callable[[Routes], None]
        if isinstance(iterable_or_module, str):
            if ':' not in iterable_or_module:
                iterable_or_module += ':' + callback
            configure_callback: IncludeRoutesCallback = import_string(iterable_or_module)
            configure_callback(self)
        else:
            self._routes.extend(list(iterable_or_module))

    def __iter__(self) -> typing.Iterator[routing.BaseRoute]:
        return iter(self._routes)

    def __len__(self) -> int:
        return len(self._routes)

    def __getitem__(self, item: typing.Any) -> typing.Any:  # pragma: nocover
        """Added to implement Sequence protocol."""
        raise NotImplementedError

    def __contains__(self, route: object) -> typing.Any:  # pragma: nocover
        raise NotImplementedError
