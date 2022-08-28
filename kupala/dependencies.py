from __future__ import annotations

import dataclasses

import inspect
import typing

if typing.TYPE_CHECKING:
    from kupala.http.requests import Request

InjectFactory = typing.Callable[["Request"], typing.Any]


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


async def generate_injections(request: Request, plan: dict[str, typing.Type[typing.Any]]) -> dict[str, typing.Any]:
    from kupala.http.requests import Request

    injections = request.path_params
    for arg_name, arg_type in plan.items():
        if arg_name in request.path_params:
            continue

        if hasattr(arg_type, "__origin__"):  # generic types
            arg_type = getattr(arg_type, "__origin__")

        if arg_type == Request:
            injections[arg_name] = request
            continue

        injection = request.app.get_dependency(arg_type)
        type_or_coro = await injection.resolve(request)

        if inspect.iscoroutine(type_or_coro):
            type_or_coro = await type_or_coro
        injections[arg_name] = type_or_coro

    return injections
