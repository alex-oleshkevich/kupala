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


def create_dispatch_chain(guards: typing.Iterable[Guard], call_next: NextGuard) -> NextGuard:
    for guard in reversed(list(guards)):
        call_next = functools.partial(guard, call_next=call_next)
    return call_next


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
        signature = inspect.signature(fn)
        parameters = dict(signature.parameters)
        request_param_name: str = ""  # empty when endpoint does not inject request

        if "request" in parameters:
            request_param_name = "request"
            request_class = parameters["request"].annotation or Request
        else:
            for param_name, param in parameters.items():
                if inspect.isclass(param.annotation) and (
                    param.annotation == Request or issubclass(param.annotation, requests.HTTPConnection)
                ):
                    request_class = param.annotation
                    request_param_name = param_name
                    break

        async def endpoint_handler(request: Request) -> Response:
            fn_arguments: dict[str, typing.Any] = {}

            for param_name, param in parameters.items():
                annotation = param.annotation

                if param_name == request_param_name:
                    request.__class__ = request_class
                    fn_arguments[request_param_name] = request
                    continue

                # if function argument is in path param, then use param value for the argument
                if param_name in request.path_params:
                    fn_arguments[param_name] = request.path_params[param_name]
                    continue

                # handle typing.Annotated[Class, injection_factory] dependencies
                if typing.get_origin(annotation) is typing.Annotated:
                    _, factory = typing.get_args(annotation)
                    dependency = await factory(request) if inspect.iscoroutinefunction(factory) else factory(request)
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
