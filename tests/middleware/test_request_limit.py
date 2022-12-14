import pytest
from starlette.responses import PlainTextResponse
from starlette.testclient import TestClient
from starlette.types import Receive, Scope, Send
from starlette.websockets import WebSocket

from kupala.middleware import RequestLimitMiddleware
from kupala.requests import Request


async def app(scope: Scope, receive: Receive, send: Send) -> None:
    request = Request(scope, receive, send)
    await request.form()
    await PlainTextResponse("")(scope, receive, send)


@pytest.mark.asyncio
async def test_request_limit_middleware_limits() -> None:
    """When request body is larger than a configured limit then 413 response to be returned."""

    client = TestClient((RequestLimitMiddleware(app, max_body_size=5)))
    assert client.post("/", data={"content": ""}).status_code == 413  # 8 bytes, message + "=" sign


@pytest.mark.asyncio
async def test_request_limit_middleware_allows() -> None:
    client = TestClient((RequestLimitMiddleware(app, max_body_size=10)))
    assert client.post("/", data={"content": ""}).status_code == 200  # 8 bytes, message + "=" sign


@pytest.mark.asyncio
async def test_disabled_request_limit_middleware() -> None:
    client = TestClient((RequestLimitMiddleware(app, max_body_size=None)))
    assert client.post("/", data={"content": ""}).status_code == 200  # 8 bytes, message + "=" sign


@pytest.mark.asyncio
async def test_request_limit_middleware_ignores_websockets() -> None:
    async def app(scope: Scope, receive: Receive, send: Send) -> None:
        ws = WebSocket(scope, receive, send)
        await ws.accept()
        await ws.receive_text()

    client = TestClient((RequestLimitMiddleware(app, max_body_size=1)))
    with client.websocket_connect("/") as session:
        session.send_text("content")
