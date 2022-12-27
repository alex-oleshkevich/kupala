import pytest
from starlette.responses import PlainTextResponse
from starlette.testclient import TestClient
from starlette.types import Receive, Scope, Send

from kupala.middleware.request_id import RequestIDMiddleware
from kupala.requests import Request
from kupala.routing import Routes
from tests.conftest import AppFactory


async def app(scope: Scope, receive: Receive, send: Send) -> None:
    request = Request(scope, receive, send)
    await PlainTextResponse(request.state.request_id)(scope, receive, send)


@pytest.mark.asyncio
async def test_generates_request_id() -> None:
    client = TestClient(RequestIDMiddleware(app))
    response = client.get("/")
    assert len(response.text) == 32
    assert response.headers["x-request-id"] == response.text


@pytest.mark.asyncio
async def test_reuses_request_id(test_app_factory: AppFactory, routes: Routes) -> None:
    client = TestClient(RequestIDMiddleware(app))
    response = client.get("/")
    assert client.get("/", headers={"x-request-id": "id"}).text == "id"
    assert response.headers["x-request-id"] == response.text
