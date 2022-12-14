from __future__ import annotations

import functools
import inspect
import typing
from starlette.concurrency import run_in_threadpool
from starlette.routing import Route
from starlette.types import ASGIApp

from kupala.guards import Guard, call_guards
from kupala.requests import Request


def route(
    path: str,
    *,
    methods: list[str] | None = None,
    name: str | None = None,
    guards: list[Guard] | None = None,
) -> typing.Callable[[typing.Callable], Route]:
    def decorator(fn: typing.Callable) -> Route:
        handler = create_view_dispatcher(fn, guards or [])

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
        guards: list[Guard] | None = None,
    ) -> typing.Callable:
        def decorator(fn: typing.Callable) -> typing.Callable:
            route_ = route(path, methods=methods, name=name, guards=guards)(fn)
            self.add(route_)
            return fn

        return decorator

    def get_or_post(self, path: str, *, name: str | None = None, guards: list[Guard] | None = None) -> typing.Callable:
        return self.route(path, methods=["get", "post"], name=name, guards=guards)

    def get(self, path: str, *, name: str | None = None, guards: list[Guard] | None = None) -> typing.Callable:
        return self.route(path, methods=["get"], name=name, guards=guards)

    def post(self, path: str, *, name: str | None = None, guards: list[Guard] | None = None) -> typing.Callable:
        return self.route(path, methods=["post"], name=name, guards=guards)

    def patch(self, path: str, *, name: str | None = None, guards: list[Guard] | None = None) -> typing.Callable:
        return self.route(path, methods=["patch"], name=name, guards=guards)

    def put(self, path: str, *, name: str | None = None, guards: list[Guard] | None = None) -> typing.Callable:
        return self.route(path, methods=["put"], name=name, guards=guards)

    def delete(self, path: str, *, name: str | None = None, guards: list[Guard] | None = None) -> typing.Callable:
        return self.route(path, methods=["delete"], name=name, guards=guards)

    __call__ = route

    def __iter__(self) -> typing.Iterator[Route]:
        return iter(self._routes)

    def __len__(self) -> int:
        return len(self._routes)

    def __repr__(self) -> str:
        routes_count = len(self._routes)
        noun = "route" if routes_count == 1 else "routes"
        return f"<{self.__class__.__name__}: {routes_count} {noun}>"


def create_view_dispatcher(
    fn: typing.Callable,
    guards: list[Guard],
) -> typing.Callable[[Request], typing.Awaitable[ASGIApp]]:
    @functools.wraps(fn)
    async def view_decorator(request: Request) -> ASGIApp:
        if dispatcher := getattr(request.state, "dependencies", None):
            return await dispatcher.dispatch_view(request, fn)

        request.__class__ = Request
        if response := await call_guards(request, guards):
            return response

        if inspect.iscoroutinefunction(fn):
            response = await fn(request)
        else:
            response = await run_in_threadpool(fn, request)

        return typing.cast(ASGIApp, response)

    return view_decorator
