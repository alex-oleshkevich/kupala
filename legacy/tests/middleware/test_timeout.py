import anyio
import pytest
from starlette.responses import PlainTextResponse
from starlette.testclient import TestClient
from starlette.types import Receive, Scope, Send

from kupala.middleware.timeout import TimeoutMiddleware


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
