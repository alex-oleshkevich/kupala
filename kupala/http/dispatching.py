from __future__ import annotations

import functools
import inspect
import typing
from starlette.concurrency import run_in_threadpool
from starlette.types import ASGIApp

from kupala.http.requests import Request


def create_view_dispatcher(fn: typing.Callable) -> typing.Callable[[Request], typing.Awaitable[ASGIApp]]:
    @functools.wraps(fn)
    async def view_decorator(request: Request) -> ASGIApp:
        # make sure view receives our request class
        request.__class__ = Request
        view_args: dict[str, typing.Any] = request.path_params

        if inspect.iscoroutinefunction(fn):
            response = await fn(request, **view_args)
        else:
            response = await run_in_threadpool(fn, request, **view_args)

        return typing.cast(ASGIApp, response)

    return view_decorator
