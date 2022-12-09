from __future__ import annotations

import dataclasses

import inspect
import typing
from starlette.concurrency import run_in_threadpool
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp, Receive, Scope, Send

from kupala.requests import Request as KupalaRequest

InjectFactory = typing.Callable[["Request"], typing.Any]


class DependencyError(Exception):
    ...


class NoDependency(DependencyError):
    ...


@dataclasses.dataclass
class Injection:
    factory: InjectFactory
    cached: bool = False
    _instance: typing.Any = None

    async def resolve(self, request: Request) -> typing.Any:
        if self._instance and self.cached:
            return self._instance

        result = self.factory(request)
        if inspect.iscoroutine(result):
            result = await result

        if self.cached:
            self._instance = result
        return result


class Injector:
    def __init__(self, injections: dict[typing.Hashable, Injection] | None = None) -> None:
        self._injections = injections or {}

    def add_dependency(
        self,
        name: typing.Hashable,
        callback: typing.Callable,
        cached: bool = False,
    ) -> None:
        self._injections[name] = Injection(factory=callback, cached=cached)

    def get_dependency(self, name: typing.Hashable) -> Injection:
        if origin := getattr(name, "__origin__", None):
            name = origin

        if name not in self._injections:
            raise NoDependency(f'No dependency factory for type "{name}"')

        return self._injections[name]

    def register(self, name: typing.Hashable, cached: bool = False) -> typing.Callable:
        def decorator(callback: typing.Callable) -> typing.Any:
            self.add_dependency(name, callback, cached)
            return callback

        return decorator

    async def generate_injections(
        self, request: Request, parameters: dict[str, inspect.Parameter]
    ) -> dict[str, typing.Any]:
        injections = {}
        for param_name, param in parameters.items():
            annotation = param.annotation

            if param_name in request.path_params:
                injections[param_name] = request.path_params[param_name]
                continue

            if typing.get_origin(annotation) is typing.Annotated:
                _, factory = typing.get_args(annotation)
                injections[param_name] = (
                    await factory(request) if inspect.iscoroutinefunction(factory) else factory(request)
                )
                continue

            if hasattr(annotation, "__origin__"):  # generic types
                annotation = getattr(annotation, "__origin__")

            if inspect.isclass(annotation):
                if annotation == Request or issubclass(annotation, Request):
                    injections[param_name] = request
                    continue

            try:
                injection = self.get_dependency(annotation)
                type_or_coro = await injection.resolve(request)

                if inspect.iscoroutine(type_or_coro):
                    type_or_coro = await type_or_coro
            except NoDependency:
                if param.default == inspect.Parameter.empty:
                    raise
                type_or_coro = None

            injections[param_name] = type_or_coro

        return injections

    async def dispatch_view(self, request: Request, callback: typing.Callable) -> Response:
        request.__class__ = KupalaRequest
        signature = inspect.signature(callback)
        parameters = dict(signature.parameters)
        view_args = await self.generate_injections(request, parameters)
        if parameters.get("request"):
            request.__class__ = parameters["request"].annotation

        if inspect.iscoroutinefunction(callback):
            response = await callback(**view_args)
        else:
            response = await run_in_threadpool(callback, **view_args)

        return typing.cast(Response, response)


class DiMiddleware:
    def __init__(self, app: ASGIApp, injector: Injector) -> None:
        self.app = app
        self.injector = injector

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        scope.setdefault("state", {})
        scope["state"]["dependencies"] = self.injector
        await self.app(scope, receive, send)
