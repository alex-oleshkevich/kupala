import pytest
from starlette.exceptions import HTTPException
from starlette.types import Receive, Scope, Send
from starlette.websockets import WebSocket

from kupala.http import WebSocketRoute, route
from kupala.http.middleware import ExceptionMiddleware, Middleware
from kupala.http.requests import Request
from kupala.http.responses import PlainTextResponse, Response
from tests.conftest import TestClientFactory


def test_handler_by_status_code(test_client_factory: TestClientFactory) -> None:
    async def on_403(request: Request, exc: Exception) -> Response:
        return Response("called")

    @route("/")
    async def index_view() -> None:
        raise HTTPException(status_code=403)

    client = test_client_factory(
        routes=[index_view], middleware=[Middleware(ExceptionMiddleware, handlers={403: on_403})]
    )
    response = client.get("/")
    assert response.text == "called"


def test_handler_by_type(test_client_factory: TestClientFactory) -> None:
    class CustomError(Exception):
        pass

    async def on_error(request: Request, exc: Exception) -> Response:
        return Response("called")

    @route("/")
    async def index_view(request: Request) -> None:
        raise CustomError()

    client = test_client_factory(
        routes=[index_view], middleware=[Middleware(ExceptionMiddleware, handlers={CustomError: on_error})]
    )

    response = client.get("/")
    assert response.text == "called"


def test_sync_handler(test_client_factory: TestClientFactory) -> None:
    class CustomError(Exception):
        pass

    def on_error(request: Request, exc: Exception) -> Response:
        return Response("called")

    @route("/")
    async def index_view() -> None:
        raise CustomError()

    client = test_client_factory(
        routes=[index_view], middleware=[Middleware(ExceptionMiddleware, handlers={CustomError: on_error})]
    )
    response = client.get("/")
    assert response.text == "called"


def test_composite_exception(test_client_factory: TestClientFactory) -> None:
    class CustomError(TypeError):
        pass

    def on_error(request: Request, exc: Exception) -> Response:
        return Response("called")

    @route("/")
    async def index_view() -> None:
        raise CustomError()

    client = test_client_factory(
        routes=[index_view], middleware=[Middleware(ExceptionMiddleware, handlers={TypeError: on_error})]
    )
    response = client.get("/")
    assert response.text == "called"


def test_should_reraise_unhandled_exception(test_client_factory: TestClientFactory) -> None:
    class CustomError(TypeError):
        pass

    @route("/")
    async def index_view(request: Request) -> None:
        raise CustomError()

    client = test_client_factory(routes=[index_view], middleware=[Middleware(ExceptionMiddleware, handlers={})])

    with pytest.raises(CustomError):
        response = client.get("/")
        assert response.text == "called"


@route("/")
class HandledExcAfterResponse:
    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        response = PlainTextResponse("OK", status_code=200)
        await response(scope, receive, send)
        raise HTTPException(status_code=406)


def test_handled_exc_after_response(test_client_factory: TestClientFactory) -> None:
    client = test_client_factory(
        routes=[HandledExcAfterResponse],  # type: ignore[list-item]
        middleware=[Middleware(ExceptionMiddleware, handlers={})],
    )

    with pytest.raises(RuntimeError):
        client.get("/")


def test_websocket_should_raise(test_client_factory: TestClientFactory) -> None:
    def raise_runtime_error(request: WebSocket) -> None:
        raise RuntimeError("Oops!")

    client = test_client_factory(
        routes=[WebSocketRoute("/", raise_runtime_error)], middleware=[Middleware(ExceptionMiddleware, handlers={})]
    )

    with pytest.raises(RuntimeError):
        with client.websocket_connect("/"):
            pass


def test_default_http_error_handler(test_client_factory: TestClientFactory) -> None:
    @route("/")
    async def index_view(request: Request) -> None:
        raise HTTPException(status_code=409)

    client = test_client_factory(routes=[index_view], middleware=[Middleware(ExceptionMiddleware, handlers={})])

    with pytest.raises(HTTPException):
        client.get("/")
