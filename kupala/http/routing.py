from __future__ import annotations

import typing
from starlette import routing
from starlette.routing import Route
from starlette.types import ASGIApp, Receive, Scope, Send

from kupala.http import Request
from kupala.http.dispatching import create_view_dispatcher
from kupala.http.guards import Guard
from kupala.http.middleware import Middleware
from kupala.http.middleware.guards import GuardsMiddleware


def apply_middleware(app: typing.Callable, middleware: typing.Iterable[Middleware]) -> ASGIApp:
    for mw in reversed(list(middleware)):
        app = mw.wrap(app)
    return app


class Mount(routing.Mount):
    def __init__(
        self,
        path: str,
        app: ASGIApp | None = None,
        routes: typing.Sequence[routing.BaseRoute] | None = None,
        name: str | None = None,
        middleware: typing.Iterable[Middleware] | None = None,
        guards: typing.Iterable[Guard] | None = None,
    ) -> None:
        middleware = list(middleware or [])

        if guards:
            middleware.append(Middleware(GuardsMiddleware, guards=guards))

        super().__init__(path, app=app, routes=routes, name=name, middleware=middleware)  # type: ignore[arg-type]


def route(
    path: str,
    *,
    methods: list[str] | None = None,
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

            async def _asgi_handler(scope: Scope, receive: Receive, send: Send) -> None:
                response = await view_handler(Request(scope, receive, send))
                await response(scope, receive, send)

            handler = apply_middleware(_asgi_handler, middleware)  # type: ignore[assignment]

        return Route(path=path, endpoint=handler, name=name, methods=methods)

    return decorator


class Routes(typing.Iterable[Route]):
    def __init__(self, routes: typing.Iterable[Route] | None = None) -> None:
        self._routes: list[Route] = list(routes or [])

    def route(
        self,
        path: str,
        *,
        methods: list[str] | None = None,
        name: str | None = None,
        guards: list[Guard] | None = None,
    ) -> typing.Callable:
        def decorator(fn: typing.Callable) -> typing.Callable:
            route_ = route(path, methods=methods, name=name, guards=guards)(fn)
            self._routes.append(route_)
            return fn

        return decorator

    __call__ = route

    def __iter__(self) -> typing.Iterator[Route]:
        return iter(self._routes)

    def __len__(self) -> int:
        return len(self._routes)

    def __repr__(self) -> str:
        routes_count = len(self._routes)
        noun = "route" if routes_count == 1 else "routes"
        return f"<{self.__class__.__name__}: {routes_count} {noun}>"
