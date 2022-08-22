import anyio
import pytest
from starlette.types import Receive, Scope, Send

from kupala.http.middleware.timeout import TimeoutMiddleware
from kupala.http.responses import PlainTextResponse
from kupala.testclient import TestClient


async def app(scope: Scope, receive: Receive, send: Send) -> None:
    await anyio.sleep(0.2)
    await PlainTextResponse("")(scope, receive, send)


@pytest.mark.asyncio
async def test_timeout_middleware() -> None:
    client = TestClient(TimeoutMiddleware(app, timeout=0.1))
    assert client.get("/").status_code == 504


@pytest.mark.asyncio
async def test_timeout_middleware_not_fails_withing_timespan() -> None:
    client = TestClient(TimeoutMiddleware(app, timeout=1))
    assert client.get("/").status_code == 200
