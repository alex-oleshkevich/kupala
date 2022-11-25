from __future__ import annotations

import functools
import inspect
import typing
from starlette.concurrency import run_in_threadpool
from starlette.routing import Route
from starlette.types import ASGIApp

from kupala.requests import Request


def route(
    path: str,
    *,
    methods: list[str] | None = None,
    name: str | None = None,
) -> typing.Callable[[typing.Callable], Route]:
    def decorator(fn: typing.Callable) -> Route:
        handler = create_view_dispatcher(fn)

        return Route(path=path, endpoint=handler, name=name, methods=methods)

    return decorator


class Routes(typing.Iterable[Route]):
    def __init__(self, routes: typing.Iterable[Route] | None = None) -> None:
        self._routes: list[Route] = list(routes or [])

    def add(self, route: Route) -> None:
        self._routes.append(route)

    def route(
        self,
        path: str,
        *,
        methods: list[str] | None = None,
        name: str | None = None,
    ) -> typing.Callable:
        def decorator(fn: typing.Callable) -> typing.Callable:
            route_ = route(path, methods=methods, name=name)(fn)
            self.add(route_)
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


def create_view_dispatcher(fn: typing.Callable) -> typing.Callable[[Request], typing.Awaitable[ASGIApp]]:
    @functools.wraps(fn)
    async def view_decorator(request: Request) -> ASGIApp:
        if dispatcher := getattr(request.state, "dependencies", None):
            return await dispatcher.dispatch_view(request, fn)

        request.__class__ = Request
        if inspect.iscoroutinefunction(fn):
            response = await fn(request)
        else:
            response = await run_in_threadpool(fn, request)

        return typing.cast(ASGIApp, response)

    return view_decorator
