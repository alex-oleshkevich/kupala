from __future__ import annotations

import functools
import importlib
import inspect
import typing
from starlette import requests
from starlette.concurrency import run_in_threadpool
from starlette.responses import Response
from starlette.routing import Route

from kupala.guards import Guard, NextGuard
from kupala.requests import Request


class InjectionError(Exception):
    ...


def create_dispatch_chain(guards: typing.Iterable[Guard], call_next: NextGuard) -> NextGuard:
    for guard in reversed(list(guards)):
        call_next = functools.partial(guard, call_next=call_next)
    return call_next


async def _patch_request(request: typing.Any, request_class: Request) -> Request:
    request.__class__ = request_class
    return request


def _generate_dependency_factories(
    fn: typing.Callable,
) -> tuple[dict[str, typing.Callable[[Request], typing.Any]], list[str], dict[str, inspect.Parameter]]:
    signature = inspect.signature(fn)
    parameters = dict(signature.parameters)
    optionals: list[str] = []
    factories: dict[str, typing.Callable] = {}
    for param_name, parameter in parameters.items():
        if param_name == "request":
            if origin := typing.get_origin(parameter.annotation):
                request_class = origin
            else:
                request_class = parameter.annotation

            factories[param_name] = functools.partial(_patch_request, request_class=request_class)
            continue

        origin = typing.get_origin(parameter.annotation) or parameter.annotation
        if inspect.isclass(origin) and issubclass(origin, requests.HTTPConnection):
            factories[param_name] = functools.partial(_patch_request, request_class=origin)
            continue

        annotation = parameter.annotation
        if origin is typing.Union:
            optional = type(None) in typing.get_args(parameter.annotation)
            if optional:
                optionals.append(param_name)
            annotation = next((value for value in typing.get_args(parameter.annotation) if value is not None))

        if origin is typing.Annotated:
            _, factory = typing.get_args(annotation)

            async def _factory(request: Request, dependency_factory: typing.Callable) -> typing.Any:
                return (
                    await dependency_factory(request)
                    if inspect.iscoroutinefunction(dependency_factory)
                    else dependency_factory(request)
                )

            factories[param_name] = functools.partial(_factory, dependency_factory=factory)
    return factories, optionals, parameters


def route(
    path: str,
    *,
    methods: list[str] | None = None,
    name: str | None = None,
    guards: list[Guard] | None = None,
) -> typing.Callable[[typing.Callable], Route]:
    """Convert endpoint callable into Route object."""

    def decorator(fn: typing.Callable) -> Route:
        factories, optionals, parameters = _generate_dependency_factories(fn)

        async def endpoint_handler(request: Request) -> Response:
            fn_arguments: dict[str, typing.Any] = {}

            for param_name, param in parameters.items():
                # if function argument is in path param, then use param value for the argument
                if param_name in request.path_params:
                    fn_arguments[param_name] = request.path_params[param_name]
                    continue

                if param_name in factories:
                    dependency = await factories[param_name](request)
                    if dependency is None and param_name not in optionals and param.default is not None:
                        raise InjectionError(
                            f'Dependency factory for argument "{param_name}" of "{fn.__name__}" returned None '
                            f'but the "{param_name}" declared as not optional.'
                        )

                    fn_arguments[param_name] = dependency

            if inspect.iscoroutinefunction(fn):
                return await fn(**fn_arguments)
            else:
                return await run_in_threadpool(fn, **fn_arguments)

        chain = create_dispatch_chain(guards or [], endpoint_handler)

        route_instance = Route(path=path, endpoint=chain, name=name, methods=methods)
        return route_instance

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


class Routes(typing.Iterable[Route]):
    def __init__(self, routes: typing.Iterable[Route | Routes] | None = None) -> None:
        self._routes: list[Route] = []
        for _route in routes or []:
            if isinstance(_route, Routes):
                self._routes.extend(_route)
            else:
                self._routes.append(_route)

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

    def options(self, path: str, *, name: str | None = None, guards: list[Guard] | None = None) -> typing.Callable:
        return self.route(path, methods=["options"], name=name, guards=guards)

    __call__ = route

    def __iter__(self) -> typing.Iterator[Route]:
        return iter(self._routes)

    def __len__(self) -> int:
        return len(self._routes)

    def __repr__(self) -> str:
        routes_count = len(self._routes)
        noun = "route" if routes_count == 1 else "routes"
        return f"<{self.__class__.__name__}: {routes_count} {noun}>"
