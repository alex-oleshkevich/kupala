from __future__ import annotations

import inspect
import typing
from starlette.concurrency import run_in_threadpool

from kupala.http.exceptions import PermissionDenied
from kupala.http.requests import Request


class Guard(typing.Protocol):  # pragma: no cover
    def __call__(self, request: Request) -> bool | None | typing.Awaitable[bool | None]:
        ...


async def call_guards(request: Request, guards: typing.Iterable[Guard]) -> None:
    """Call route guards."""
    for guard in guards:
        if inspect.iscoroutinefunction(guard):
            result = guard(request)
        else:
            result = await run_in_threadpool(guard, request)

        if inspect.iscoroutine(result):
            result = await result

        if result is False:
            raise PermissionDenied("You are not allowed to access this page.")
