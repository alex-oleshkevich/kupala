import pytest

from kupala.http import PlainTextResponse, Request, Routes
from kupala.http.middleware import Middleware
from kupala.http.middleware.method_override import MethodOverrideMiddleware
from kupala.testclient import TestClient
from tests.conftest import TestAppFactory


@pytest.mark.asyncio
async def test_overrides_method(test_app_factory: TestAppFactory, routes: Routes) -> None:
    async def view(request: Request) -> PlainTextResponse:
        return PlainTextResponse(request.method)

    routes.add('/', view, methods=['DELETE'])
    app = test_app_factory(
        middleware=[Middleware(MethodOverrideMiddleware)],
        routes=routes,
    )

    client = TestClient(app)
    assert client.post('/', data={'_method': 'delete'}).text == 'DELETE'


@pytest.mark.asyncio
async def test_bypass_read_methods(test_app_factory: TestAppFactory, routes: Routes) -> None:
    async def view(request: Request) -> PlainTextResponse:
        return PlainTextResponse(request.method)

    routes.add('/', view, methods=['GET'])
    app = test_app_factory(
        middleware=[Middleware(MethodOverrideMiddleware)],
        routes=routes,
    )

    client = TestClient(app)
    assert client.get('/').text == 'GET'