from __future__ import annotations

import dataclasses

import inspect
import typing

if typing.TYPE_CHECKING:
    from kupala.http.requests import Request

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


async def generate_injections(request: Request, parameters: dict[str, inspect.Parameter]) -> dict[str, typing.Any]:
    from kupala.http.requests import Request

    injections = request.path_params
    for param_name, param in parameters.items():
        if param_name in request.path_params:
            continue

        if hasattr(param.annotation, "__origin__"):  # generic types
            param = getattr(param, "__origin__")

        if param.annotation == Request:
            injections[param_name] = request
            continue

        try:
            injection = request.app.dependencies.get_dependency(param.annotation)
            type_or_coro = await injection.resolve(request)

            if inspect.iscoroutine(type_or_coro):
                type_or_coro = await type_or_coro
        except NoDependency:
            if param.default == inspect.Parameter.empty:
                raise
            type_or_coro = None

        injections[param_name] = type_or_coro

    return injections
