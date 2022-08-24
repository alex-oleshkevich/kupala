from __future__ import annotations

import functools
import inspect
import typing
from starlette.concurrency import run_in_threadpool
from starlette.types import ASGIApp

from kupala.dependencies import Inject
from kupala.http.requests import Request


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

            def from_path(request: Request, param_name: str) -> typing.Any:
                return request.path_params[param_name]

            injection_plan[arg_name] = Inject(factory=functools.partial(from_path, param_name=arg_name))

    return injection_plan


def create_view_dispatcher(
    fn: typing.Callable, inject: dict[str, Inject]
) -> typing.Callable[[Request], typing.Awaitable[ASGIApp]]:
    injection_plan = generate_injection_plan(fn, inject)

    @functools.wraps(fn)
    async def view_decorator(request: Request) -> ASGIApp:
        # make sure view receives our request class
        request.__class__ = Request
        view_args: dict[str, typing.Any] = {}
        for arg_name, arg_factory in injection_plan.items():
            if inspect.iscoroutinefunction(arg_factory.factory):
                view_args[arg_name] = await arg_factory.factory(request)
            else:
                view_args[arg_name] = arg_factory.factory(request)

        if inspect.iscoroutinefunction(fn):
            response = await fn(**view_args)
        else:
            response = await run_in_threadpool(fn, **view_args)

        return typing.cast(ASGIApp, response)

    return view_decorator
