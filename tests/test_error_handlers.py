import pytest
from starlette.exceptions import HTTPException
from starlette.types import Receive, Scope, Send
from starlette.websockets import WebSocket

from kupala.http import Routes
from kupala.http.middleware import ExceptionMiddleware, Middleware
from kupala.http.requests import Request
from kupala.http.responses import PlainTextResponse, Response
from tests.conftest import TestClientFactory


def test_handler_by_status_code(test_client_factory: TestClientFactory, routes: Routes) -> None:
    async def on_403(request: Request, exc: Exception) -> Response:
        return Response("called")

    async def index_view() -> None:
        raise HTTPException(status_code=403)

    routes.add("/", index_view)
    client = test_client_factory(routes=routes, middleware=[Middleware(ExceptionMiddleware, handlers={403: on_403})])
    response = client.get("/")
    assert response.text == "called"


def test_handler_by_type(test_client_factory: TestClientFactory, routes: Routes) -> None:
    class CustomError(Exception):
        pass

    async def on_error(request: Request, exc: Exception) -> Response:
        return Response("called")

    async def index_view(request: Request) -> None:
        raise CustomError()

    routes.add("/", index_view)
    client = test_client_factory(
        routes=routes, middleware=[Middleware(ExceptionMiddleware, handlers={CustomError: on_error})]
    )

    response = client.get("/")
    assert response.text == "called"


def test_sync_handler(test_client_factory: TestClientFactory, routes: Routes) -> None:
    class CustomError(Exception):
        pass

    def on_error(request: Request, exc: Exception) -> Response:
        return Response("called")

    async def index_view() -> None:
        raise CustomError()

    routes.add("/", index_view)
    client = test_client_factory(
        routes=routes, middleware=[Middleware(ExceptionMiddleware, handlers={CustomError: on_error})]
    )
    response = client.get("/")
    assert response.text == "called"


def test_composite_exception(test_client_factory: TestClientFactory, routes: Routes) -> None:
    class CustomError(TypeError):
        pass

    def on_error(request: Request, exc: Exception) -> Response:
        return Response("called")

    async def index_view() -> None:
        raise CustomError()

    routes.add("/", index_view)
    client = test_client_factory(
        routes=routes, middleware=[Middleware(ExceptionMiddleware, handlers={TypeError: on_error})]
    )
    response = client.get("/")
    assert response.text == "called"


def test_should_reraise_unhandled_exception(test_client_factory: TestClientFactory, routes: Routes) -> None:
    class CustomError(TypeError):
        pass

    async def index_view(request: Request) -> None:
        raise CustomError()

    routes.add("/", index_view)
    client = test_client_factory(routes=routes, middleware=[Middleware(ExceptionMiddleware, handlers={})])

    with pytest.raises(CustomError):
        response = client.get("/")
        assert response.text == "called"


class HandledExcAfterResponse:
    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        response = PlainTextResponse("OK", status_code=200)
        await response(scope, receive, send)
        raise HTTPException(status_code=406)


def test_handled_exc_after_response(test_client_factory: TestClientFactory, routes: Routes) -> None:
    routes.add("/", HandledExcAfterResponse())
    client = test_client_factory(routes=routes, middleware=[Middleware(ExceptionMiddleware, handlers={})])

    with pytest.raises(RuntimeError):
        client.get("/")


def test_websocket_should_raise(test_client_factory: TestClientFactory, routes: Routes) -> None:
    def raise_runtime_error(request: WebSocket) -> None:
        raise RuntimeError("Oops!")

    routes.websocket("/", raise_runtime_error)
    client = test_client_factory(routes=routes, middleware=[Middleware(ExceptionMiddleware, handlers={})])

    with pytest.raises(RuntimeError):
        with client.websocket_connect("/"):
            pass


def test_default_http_error_handler(test_client_factory: TestClientFactory, routes: Routes) -> None:
    async def index_view(request: Request) -> None:
        raise HTTPException(status_code=409)

    routes.add("/", index_view)
    client = test_client_factory(routes=routes, middleware=[Middleware(ExceptionMiddleware, handlers={})])

    response = client.get("/")
    assert response.status_code == 409


def test_default_error_handler_for_json(test_client_factory: TestClientFactory, routes: Routes) -> None:
    async def view() -> None:
        raise HTTPException(detail="Ooops", status_code=405)

    routes.add("/", view)
    client = test_client_factory(debug=False, routes=routes, middleware=[Middleware(ExceptionMiddleware, handlers={})])

    response = client.get("/", headers={"accept": "application/json"})
    assert response.status_code == 405
    assert response.headers["content-type"] == "application/json"
    assert response.json() == {
        "message": "Ooops",
        "errors": {},
    }


def test_default_error_handler_for_json_in_debug(test_client_factory: TestClientFactory, routes: Routes) -> None:
    async def view() -> None:
        raise HTTPException(detail="Ooops", status_code=405)

    routes.add("/", view)
    client = test_client_factory(routes=routes, middleware=[Middleware(ExceptionMiddleware, handlers={})])

    response = client.get("/", headers={"accept": "application/json"})
    assert response.status_code == 405
    assert response.headers["content-type"] == "application/json"
    assert response.json() == {
        "message": "Ooops",
        "errors": {},
        "exception_type": "starlette.exceptions.HTTPException",
        "exception": "HTTPException(status_code=405, detail='Ooops')",
    }


def test_default_error_handler_not_modified_in_debug(test_client_factory: TestClientFactory, routes: Routes) -> None:
    async def view() -> None:
        raise HTTPException(detail="Ooops", status_code=304)

    routes.add("/", view)
    client = test_client_factory(routes=routes, middleware=[Middleware(ExceptionMiddleware, handlers={})])

    response = client.get("/")
    assert response.status_code == 304


def test_default_error_handler_empty_response_in_debug(test_client_factory: TestClientFactory, routes: Routes) -> None:
    async def view() -> None:
        raise HTTPException(detail="Ooops", status_code=204)

    routes.add("/", view)
    client = test_client_factory(routes=routes, middleware=[Middleware(ExceptionMiddleware, handlers={})])
    response = client.get("/")
    assert response.status_code == 204


def test_default_error_handler_in_debug(test_client_factory: TestClientFactory, routes: Routes) -> None:
    async def view() -> None:
        raise HTTPException(detail="Ooops", status_code=500)

    routes.add("/", view)
    client = test_client_factory(routes=routes, middleware=[Middleware(ExceptionMiddleware, handlers={})])
    response = client.get("/")
    assert response.status_code == 500
    assert response.text == "Ooops"
