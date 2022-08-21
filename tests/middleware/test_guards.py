from starlette.types import Receive, Scope, Send
from unittest import mock

from kupala.http import Request, Response
from kupala.http.middleware.guards import GuardsMiddleware
from kupala.testclient import TestClient


def test_middleware_calls_guards() -> None:
    sync_guard_called = mock.MagicMock()
    async_guard_called = mock.MagicMock()

    def sync_guard(request: Request) -> None:
        sync_guard_called()

    async def async_guard(request: Request) -> None:
        async_guard_called()

    async def app(scope: Scope, receive: Receive, send: Send) -> None:
        await Response("")(scope, receive, send)

    app = GuardsMiddleware(app, guards=[sync_guard, async_guard])
    client = TestClient(app)
    client.get("/")
    sync_guard_called.assert_called_once()
    async_guard_called.assert_called_once()
