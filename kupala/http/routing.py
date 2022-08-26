from __future__ import annotations

import os
import typing
from starlette import routing
from starlette.routing import Router
from starlette.staticfiles import StaticFiles
from starlette.types import ASGIApp, Receive, Scope, Send

from kupala.http import Request
from kupala.http.dispatching import create_view_dispatcher
from kupala.http.file_server import FileServer
from kupala.http.guards import Guard
from kupala.http.middleware import Middleware
from kupala.http.middleware.guards import GuardsMiddleware
from kupala.storages.storages import Storage


def apply_middleware(app: typing.Callable, middleware: typing.Iterable[Middleware]) -> ASGIApp:
    for mw in reversed(list(middleware)):
        app = mw.wrap(app)
    return app


class Mount(routing.Mount):
    def __init__(
        self,
        path: str,
        app: ASGIApp | None = None,
        routes: typing.Iterable[routing.BaseRoute] | None = None,
        name: str | None = None,
        middleware: typing.Iterable[Middleware] | None = None,
        guards: typing.Iterable[Guard] | None = None,
    ) -> None:
        assert app or routes, "Either ASGI app or router required."

        middleware = list(middleware or [])

        if guards:
            middleware.append(Middleware(GuardsMiddleware, guards=guards))

        if app is not None:
            self._base_app = app
        else:
            assert routes
            self._base_app = Router(routes=list(routes))

        app = apply_middleware(self._base_app, middleware)
        super().__init__(path, app=app, name=name)

    @property
    def routes(self) -> list[routing.BaseRoute]:
        return getattr(self._base_app, "routes", [])


class Host(routing.Host):
    def __init__(
        self,
        host: str,
        app: ASGIApp | None = None,
        routes: typing.Iterable[routing.BaseRoute] | None = None,
        name: str | None = None,
        middleware: typing.Iterable[Middleware] | None = None,
        guards: list[Guard] | None = None,
    ) -> None:
        assert app or routes, "Either ASGI app or router required."

        middleware = list(middleware or [])
        if guards:
            middleware.append(Middleware(GuardsMiddleware, guards=guards))

        if app is not None:
            self._base_app = app
        else:
            assert routes
            self._base_app = Router(routes=list(routes))

        app = apply_middleware(self._base_app, middleware)
        super().__init__(host, app=app, name=name)

    @property
    def routes(self) -> list[routing.BaseRoute]:
        return getattr(self._base_app, "routes", [])


class Route(routing.Route):
    def __repr__(self) -> str:
        return f"<Route: path={self.path}, methods={self.methods}, name={self.name}>"


def route(
    path: str,
    *,
    methods: list[str] = None,
    name: str | None = None,
    guards: list[Guard] | None = None,
    middleware: list[Middleware] | None = None,
) -> typing.Callable[[typing.Callable], Route]:
    middleware = middleware or []
    if guards:
        middleware.append(Middleware(GuardsMiddleware, guards=guards))

    def decorator(fn: typing.Callable) -> Route:
        view_handler = handler = create_view_dispatcher(fn)

        if middleware:

            class ASGIHandler:
                async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
                    response = await view_handler(Request(scope, receive, send))
                    await response(scope, receive, send)

            handler = _asgi_proxy(apply_middleware(ASGIHandler(), middleware))  # type: ignore[assignment]

        return Route(path=path, endpoint=handler, name=name, methods=methods)

    return decorator


def _asgi_proxy(fn: ASGIApp) -> ASGIApp:
    class ASGIProxy:
        async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
            await fn(scope, receive, send)

    return ASGIProxy()


def group(
    path: str,
    routes: typing.Iterable[routing.BaseRoute],
    *,
    middleware: typing.Iterable[Middleware] | None = None,
    guards: typing.Iterable[Guard] | None = None,
) -> Mount:
    """Allows to group routes under common prefix."""
    return Mount(path, routes=routes, middleware=middleware, guards=guards)


def static_files(
    path: str,
    directory: str | os.PathLike[str] | None = None,
    packages: list[str | tuple[str, str]] | None = None,
    *,
    name: str = "static",
    html: bool = False,
    check_dir: bool = True,
    middleware: typing.Iterable[Middleware] | None = None,
    guards: typing.Iterable[Guard] | None = None,
) -> Mount:
    return Mount(
        path=path,
        middleware=middleware,
        name=name,
        guards=guards,
        app=StaticFiles(directory=directory, packages=packages, html=html, check_dir=check_dir),
    )


def file_server(
    path: str,
    *,
    storage: Storage,
    name: str | None = None,
    inline: bool = False,
    middleware: typing.Iterable[Middleware] | None = None,
    guards: typing.Iterable[Guard] | None = None,
) -> Mount:
    return Mount(
        path=path,
        name=name,
        middleware=middleware,
        guards=guards,
        app=FileServer(storage=storage, as_attachment=inline),
    )


class Routes(typing.Iterable[Route]):
    def __init__(self, routes: typing.Iterable[Route] | None = None) -> None:
        self._routes: list[Route] = list(routes or [])

    def route(
        self,
        path: str,
        *,
        methods: list[str] = None,
        name: str | None = None,
        guards: list[Guard] | None = None,
    ) -> typing.Callable[[typing.Callable], Route]:
        def decorator(fn: typing.Callable) -> Route:
            route_ = route(path, methods=methods, name=name, guards=guards)(fn)
            self._routes.append(route_)
            return route_

        return decorator

    __call__ = route

    def __iter__(self) -> typing.Iterator[Route]:
        return iter(self._routes)

    def __len__(self) -> int:
        return len(self._routes)
