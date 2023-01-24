from __future__ import annotations

import typing
from starlette.requests import Request
from starlette.responses import Response


class NextGuard(typing.Protocol):  # pragma: no cover
    async def __call__(self, request: Request) -> Response:
        ...


class Guard(typing.Protocol):  # pragma: no cover
    """
    Guards protect views from unauthorized access.

    The guard function should raise HTTPException or return a Response.
    """

    async def __call__(self, request: Request, call_next: NextGuard) -> Response:
        ...
