import anyio
import pytest

from kupala.application import Kupala
from kupala.middleware import Middleware
from kupala.middleware.timeout import TimeoutMiddleware
from kupala.responses import PlainTextResponse
from kupala.testclient import TestClient


@pytest.mark.asyncio
async def test_timeout_middleware() -> None:
    async def view() -> PlainTextResponse:
        await anyio.sleep(0.2)
        return PlainTextResponse('')

    app = Kupala(
        middleware=[
            Middleware(TimeoutMiddleware, timeout=0.1),
        ]
    )
    app.routes.any('/', view)

    client = TestClient(app)
    assert client.get('/').status_code == 504


@pytest.mark.asyncio
async def test_timeout_middleware_not_fails_withing_timespan() -> None:
    async def view() -> PlainTextResponse:
        return PlainTextResponse('')

    app = Kupala(
        middleware=[
            Middleware(TimeoutMiddleware),
        ]
    )
    app.routes.any('/', view)

    client = TestClient(app)
    assert client.get('/').status_code == 200
