import anyio
import pytest

from kupala.http import Routes
from kupala.http.middleware import Middleware
from kupala.http.middleware.timeout import TimeoutMiddleware
from kupala.http.responses import PlainTextResponse
from kupala.testclient import TestClient
from tests.conftest import TestAppFactory


@pytest.mark.asyncio
async def test_timeout_middleware(test_app_factory: TestAppFactory, routes: Routes) -> None:
    async def view() -> PlainTextResponse:
        await anyio.sleep(0.2)
        return PlainTextResponse('')  # pragma: nocover

    routes.add('/', view)
    app = test_app_factory(
        routes=routes,
        middleware=[Middleware(TimeoutMiddleware, timeout=0.1)],
    )

    client = TestClient(app)
    assert client.get('/').status_code == 504


@pytest.mark.asyncio
async def test_timeout_middleware_not_fails_withing_timespan(test_app_factory: TestAppFactory, routes: Routes) -> None:
    async def view() -> PlainTextResponse:
        return PlainTextResponse('')

    routes.add('/', view)
    app = test_app_factory(
        routes=routes,
        middleware=[Middleware(TimeoutMiddleware)],
    )

    client = TestClient(app)
    assert client.get('/').status_code == 200
