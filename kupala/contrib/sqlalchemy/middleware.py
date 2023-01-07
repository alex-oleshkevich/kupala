from __future__ import annotations

from sqlalchemy.ext.asyncio import async_sessionmaker
from starlette.types import ASGIApp, Receive, Scope, Send


class DbSessionMiddleware:
    def __init__(self, app: ASGIApp, async_session: async_sessionmaker) -> None:
        self.app = app
        self.async_session = async_session

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        scope.setdefault("state", {})
        async with self.async_session() as session:
            scope["state"]["db"] = session
            await self.app(scope, receive, send)
