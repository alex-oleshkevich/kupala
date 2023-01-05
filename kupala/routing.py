from __future__ import annotations

import functools
import importlib
import inspect
import typing
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import BaseRoute, Route

from kupala.dependencies import Context, Dependency, DependencyResolver
from kupala.guards import Guard, NextGuard


def create_dispatch_chain(guards: typing.Iterable[Guard], call_next: NextGuard) -> NextGuard:
    for guard in reversed(list(guards)):
        call_next = functools.partial(guard, call_next=call_next)
    return call_next


def _patch_request(request: typing.Any, request_class: type[Request]) -> Request:
    request.__class__ = request_class
    return request


def route(
    path: str,
    *,
    methods: list[str] | None = None,
    name: str | None = None,
    guards: list[Guard] | None = None,
) -> typing.Callable[[typing.Callable], Route]:
    """Convert endpoint callable into Route object."""

    def decorator(fn: typing.Callable) -> Route:
        request_class = Request
        request_param_name: str = ""
        signature = inspect.signature(fn)
        for parameter in signature.parameters.values():
            origin = typing.get_origin(parameter.annotation) or parameter.annotation
            if origin == Request or issubclass(origin, Request):
                request_param_name = parameter.name
                request_class = origin
                break

        def request_factory(context: Context) -> Request:
            return _patch_request(context.conn, request_class)

        request_override = Dependency(
            type=request_class,
            param_name=request_param_name,
            optional=False,
            default_value=inspect.Parameter.empty,
            factory=request_factory,
        )
        callback = DependencyResolver.from_callable(fn, overrides={request_param_name: request_override})

        @functools.wraps(fn)
        async def endpoint_handler(request: Request) -> Response:
            return await callback.resolve(request)

        chain = create_dispatch_chain(guards or [], endpoint_handler)

        return Route(path=path, endpoint=chain, name=name, methods=methods)

    return decorator


def include(module_name: str, variable_name: str = "routes") -> Routes:
    """
    Include routes from another file.

    Usage:
        routes = Routes(
            include('admin.routes'),
            include('user.routes'),
        )
    """
    mod = importlib.import_module(module_name)
    return getattr(mod, variable_name)


def include_all(modules: typing.Iterable[str], variable_name: str = "routes") -> Routes:
    """
    Shortcut to import multiple modules at once.

    Usage:
        routes = Routes(
            include_all([
                'admin.routes',
                'user.routes',
            ]),
        )
    """
    routes: list[BaseRoute] = []
    for module_name in modules:
        routes.extend(include(module_name, variable_name))
    return Routes(routes)


class Routes(typing.Sequence[BaseRoute]):
    def __init__(self, routes: typing.Iterable[BaseRoute | Route | Routes] | None = None) -> None:
        self._routes: list[BaseRoute] = []
        for _route in routes or []:
            if isinstance(_route, Routes):
                self._routes.extend(_route)
            else:
                self._routes.append(_route)

    def add(self, route: BaseRoute) -> None:
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

    def options(self, path: str, *, name: str | None = None, guards: list[Guard] | None = None) -> typing.Callable:
        return self.route(path, methods=["options"], name=name, guards=guards)

    __call__ = route

    def __iter__(self) -> typing.Iterator[BaseRoute]:
        return iter(self._routes)

    def __len__(self) -> int:
        return len(self._routes)

    def __repr__(self) -> str:
        routes_count = len(self._routes)
        noun = "route" if routes_count == 1 else "routes"
        return f"<{self.__class__.__name__}: {routes_count} {noun}>"

    @typing.overload
    def __getitem__(self, index: int) -> BaseRoute:
        ...

    @typing.overload
    def __getitem__(self, index: slice) -> typing.Sequence[BaseRoute]:
        ...

    def __getitem__(self, index: int | slice) -> BaseRoute | typing.Sequence[BaseRoute]:
        return self._routes[index]
