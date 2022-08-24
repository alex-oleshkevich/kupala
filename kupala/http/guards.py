from __future__ import annotations

import inspect
import typing

from kupala.http.requests import Request
from kupala.http.responses import Response


class Guard(typing.Protocol):  # pragma: no cover
    """
    Guards protect views from unauthorized access.

    The guard function should raise HTTPException or return a Response.
    """

    def __call__(self, request: Request) -> Response | None | typing.Awaitable[None | Response]:
        ...


class GuardInterrupt(Exception):
    def __init__(self, response: Response) -> None:
        self.response = response


async def call_guards(request: Request, guards: typing.Iterable[Guard]) -> Response | None:
    """Call route guards."""
    for guard in guards:
        if inspect.iscoroutinefunction(guard):
            result = await guard(request)  # type: ignore[misc]
        else:
            result = guard(request)

        if isinstance(result, Response):
            return result
    return None
