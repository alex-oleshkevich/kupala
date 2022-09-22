from __future__ import annotations

import functools
import inspect
import typing
from starlette.concurrency import run_in_threadpool
from starlette.types import ASGIApp

from kupala.dependencies import generate_injections
from kupala.http.requests import Request


def create_view_dispatcher(fn: typing.Callable) -> typing.Callable[[Request], typing.Awaitable[ASGIApp]]:
    signature = inspect.signature(fn)
    parameters = dict(signature.parameters)

    @functools.wraps(fn)
    async def view_decorator(request: Request) -> ASGIApp:
        # make sure view receives our request class
        request.__class__ = Request
        view_args = await generate_injections(request, parameters)

        if inspect.iscoroutinefunction(fn):
            response = await fn(**view_args)
        else:
            response = await run_in_threadpool(fn, **view_args)

        return typing.cast(ASGIApp, response)

    return view_decorator
