from __future__ import annotations

import functools
import inspect
import typing
from contextlib import AsyncExitStack, ExitStack
from starlette.concurrency import run_in_threadpool

from kupala.http import Response
from kupala.http.guards import Guard, call_guards
from kupala.http.requests import Request


def detect_request_class(endpoint: typing.Callable) -> typing.Type[Request]:
    """
    Detect which request class to use for this endpoint.

    If endpoint does not have `request` argument, or it is not type-hinted then default request class returned.
    """
    args = typing.get_type_hints(endpoint)
    return args.get("request", Request)


async def resolve_injections(
    request: Request,
    endpoint: typing.Callable,
    sync_stack: ExitStack,
    async_stack: AsyncExitStack,
) -> dict[str, typing.Any]:
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


def create_view_dispatcher(
    fn: typing.Callable,
    guards: list[Guard],
) -> typing.Callable[[Request], typing.Awaitable[Response]]:
    request_class = detect_request_class(fn)

    @functools.wraps(fn)
    async def view_decorator(request: Request) -> Response:
        request = request_class(request.scope, request.receive, request._send)
        await call_guards(request, guards or [])

        with ExitStack() as sync_stack:
            async with AsyncExitStack() as async_stack:
                args = await resolve_injections(request, fn, sync_stack, async_stack)
                if inspect.iscoroutinefunction(fn):
                    response = await fn(**args)
                else:
                    response = await run_in_threadpool(fn, **args)
        return response

    return view_decorator
