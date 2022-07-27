import pytest
from starlette.types import Receive, Scope, Send
from starlette.websockets import WebSocket

from kupala.http import Route, Routes
from kupala.http.middleware import Middleware
from kupala.http.middleware.request_limit import RequestLimitMiddleware
from kupala.http.requests import Request
from kupala.http.responses import PlainTextResponse
from kupala.testclient import TestClient
from tests.conftest import TestAppFactory


@pytest.mark.asyncio
async def test_request_limit_middleware_limits(test_app_factory: TestAppFactory) -> None:
    """When request body is larger than a configured limit then 413 response to
    be returned."""

    async def view(request: Request) -> PlainTextResponse:
        await request.form()
        return PlainTextResponse('')

    app = test_app_factory(
        routes=Routes([Route('/', view, methods=['post'])]),
        middleware=[
            Middleware(RequestLimitMiddleware, max_body_size=5),
        ],
    )

    client = TestClient(app)
    assert client.post('/', data={'content': ''}).status_code == 413  # 8 bytes, message + "=" sign


@pytest.mark.asyncio
async def test_request_limit_middleware_allows(test_app_factory: TestAppFactory) -> None:
    async def view(request: Request) -> PlainTextResponse:
        await request.form()
        return PlainTextResponse('')

    app = test_app_factory(
        routes=Routes([Route('/', view, methods=['post'])]),
        middleware=[
            Middleware(RequestLimitMiddleware, max_body_size=10),
        ],
    )

    client = TestClient(app)
    assert client.post('/', data={'content': ''}).status_code == 200  # 8 bytes, message + "=" sign


@pytest.mark.asyncio
async def test_disabled_request_limit_middleware(test_app_factory: TestAppFactory) -> None:
    async def view(request: Request) -> PlainTextResponse:
        await request.form()
        return PlainTextResponse('')

    app = test_app_factory(
        routes=Routes([Route('/', view, methods=['post'])]),
        middleware=[
            Middleware(RequestLimitMiddleware, max_body_size=None),
        ],
    )

    client = TestClient(app)
    assert client.post('/', data={'content': ''}).status_code == 200  # 8 bytes, message + "=" sign


@pytest.mark.asyncio
async def test_request_limit_middleware_ignores_websockets() -> None:
    async def app(scope: Scope, receive: Receive, send: Send) -> None:
        ws = WebSocket(scope, receive, send)
        await ws.accept()
        await ws.receive_text()

    app = RequestLimitMiddleware(app, max_body_size=1)

    client = TestClient(app)
    with client.websocket_connect('/') as session:
        session.send_text('content')
