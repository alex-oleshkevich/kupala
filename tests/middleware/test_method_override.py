import pytest
from starlette.types import Receive, Scope, Send

from kupala.http import PlainTextResponse, Request
from kupala.http.middleware.method_override import MethodOverrideMiddleware
from kupala.testclient import TestClient


async def app(scope: Scope, receive: Receive, send: Send) -> None:
    request = Request(scope, receive, send)
    await PlainTextResponse(request.method)(scope, receive, send)


@pytest.mark.asyncio
async def test_overrides_method() -> None:
    client = TestClient(MethodOverrideMiddleware(app))
    assert client.post("/", data={"_method": "delete"}).text == "DELETE"


@pytest.mark.asyncio
async def test_bypass_read_methods() -> None:
    client = TestClient(MethodOverrideMiddleware(app))
    assert client.get("/").text == "GET"
