from __future__ import annotations

import functools
import inspect
import typing
from starlette.concurrency import run_in_threadpool

from kupala.dependencies import Inject
from kupala.http import Response
from kupala.http.requests import Request


def detect_request_class(endpoint: typing.Callable) -> typing.Type[Request]:
    """
    Detect which request class to use for this endpoint.

    If endpoint does not have `request` argument, or it is not type-hinted then default request class returned.
    """
    args = typing.get_type_hints(endpoint)
    return args.get("request", Request)


async def resolve_injections(request: Request, endpoint: typing.Callable) -> dict[str, typing.Any]:
    """
    Read endpoint signature and extract injections types. These injections will be resolved into actual service
    instances. Dependency injections and path parameters are merged.

    Return value of `from_request` can be a generator. In this case we convert it into context manager and add to
    sync/async exit stack.
    """
    injections = {}

    args = typing.get_type_hints(endpoint)
    inspect.signature(endpoint)
    for arg_name, arg_type in args.items():
        if arg_name == "return":
            continue

        if arg_type == type(request):
            injections[arg_name] = request
            continue

        if arg_name in request.path_params:
            injections[arg_name] = request.path_params[arg_name]
            continue
        else:
            continue

    return injections


def generate_injection_plan(fn: typing.Callable, injections: dict[str, Inject]) -> dict[str, Inject]:
    injection_plan: dict[str, Inject] = {}
    args = typing.get_type_hints(fn)
    for arg, factory in args.items():
        if arg == "return":
            continue

        if factory == Request or issubclass(factory, Request):
            injection_plan[arg] = Inject(factory=lambda request: request)
            continue

        if arg in injections:
            injection_plan[arg] = injections[arg]
        else:

            def from_path(request: Request, param_name: str) -> typing.Any:
                return request.path_params[param_name]

            injection_plan[arg] = Inject(factory=functools.partial(from_path, param_name=arg))

    return injection_plan


def create_view_dispatcher(
    fn: typing.Callable, inject: dict[str, Inject]
) -> typing.Callable[[Request], typing.Awaitable[Response]]:
    injection_plan = generate_injection_plan(fn, inject)

    @functools.wraps(fn)
    async def view_decorator(request: Request) -> Response:
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
        return response

    return view_decorator
