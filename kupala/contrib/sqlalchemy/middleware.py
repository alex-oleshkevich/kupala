from __future__ import annotations

from starlette.types import ASGIApp, Receive, Scope, Send

from kupala.contrib.sqlalchemy.manager import DatabaseManager


class DbSessionMiddleware:
    def __init__(self, app: ASGIApp, manager: DatabaseManager) -> None:
        self.app = app
        self.manager = manager

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        scope.setdefault("state", {})
        async with self.manager.session() as session:
            scope["state"]["dbsession"] = session
            await self.app(scope, receive, send)
