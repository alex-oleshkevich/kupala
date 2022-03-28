import pytest

from kupala.http import PlainTextResponse, Request, Routes
from kupala.http.middleware import Middleware
from kupala.http.middleware.request_id import RequestIDMiddleware
from kupala.testclient import TestClient
from tests.conftest import TestAppFactory


@pytest.mark.asyncio
async def test_generates_request_id(test_app_factory: TestAppFactory, routes: Routes) -> None:
    async def view(request: Request) -> PlainTextResponse:
        return PlainTextResponse(request.id)

    routes.add('/', view)
    app = test_app_factory(
        routes=routes,
        middleware=[Middleware(RequestIDMiddleware)],
    )

    client = TestClient(app)
    response = client.get('/')
    assert len(response.text) == 32
    assert response.headers['x-request-id'] == response.text


@pytest.mark.asyncio
async def test_reuses_request_id(test_app_factory: TestAppFactory, routes: Routes) -> None:
    async def view(request: Request) -> PlainTextResponse:
        return PlainTextResponse(request.id)

    routes.add('/', view)
    app = test_app_factory(
        routes=routes,
        middleware=[Middleware(RequestIDMiddleware)],
    )

    client = TestClient(app)
    assert client.get('/', headers={'x-request-id': 'id'}).text == 'id'
