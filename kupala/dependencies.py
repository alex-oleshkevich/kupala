from __future__ import annotations

import dataclasses

import functools
import inspect
import typing
from starlette.concurrency import run_in_threadpool
from starlette.types import ASGIApp

from kupala.http.requests import Request

_T = typing.TypeVar("_T", covariant=True)

InjectFactory = typing.Callable[[Request], _T | typing.Awaitable[_T] | "Inject"]


@dataclasses.dataclass
class Inject(typing.Generic[_T]):
    factory: InjectFactory[_T]


def from_path(request: Request, param_name: str) -> typing.Any:
    return request.path_params[param_name]


def generate_injection_plan(fn: typing.Callable, injections: dict[str, Inject]) -> dict[str, Inject]:
    injection_plan: dict[str, Inject] = {}
    args = typing.get_type_hints(fn)
    for arg_name, arg_type in args.items():
        if arg_name == "return":
            continue

        if arg_type == Request or arg_name == "request":
            injection_plan[arg_name] = Inject(factory=lambda request: request)
            continue

        if arg_name in injections:
            injection_plan[arg_name] = injections[arg_name]
        else:

            injection_plan[arg_name] = Inject(factory=functools.partial(from_path, param_name=arg_name))

    return injection_plan


def inject(**injections: InjectFactory | Inject) -> typing.Callable:
    # fix injection
    specs = {
        arg: factory if isinstance(factory, Inject) else Inject(factory=factory) for arg, factory in injections.items()
    }

    def wrapper(fn: typing.Callable) -> typing.Callable:
        injection_plan = generate_injection_plan(fn, specs)

        async def decorator(request: Request, **_: typing.Any) -> ASGIApp:
            view_args: dict[str, typing.Any] = {}
            for arg_name, arg_factory in injection_plan.items():
                if inspect.iscoroutinefunction(arg_factory.factory):
                    view_args[arg_name] = await arg_factory.factory(request)  # type: ignore[misc]
                else:
                    view_args[arg_name] = arg_factory.factory(request)

            if inspect.iscoroutinefunction(fn):
                return await fn(**view_args)
            return await run_in_threadpool(fn, **view_args)

        return decorator

    return wrapper
