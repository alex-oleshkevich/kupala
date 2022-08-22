import typing
from unittest import mock

from kupala.http.dispatching import route
from kupala.http.requests import Request
from kupala.http.responses import JSONResponse, PlainTextResponse
from tests.conftest import TestClientFactory


def test_route_decorator(test_client_factory: TestClientFactory) -> None:
    @route("/", methods=["get", "post"], name="index")
    async def view(request: Request) -> typing.NoReturn:
        ...

    assert view.path == "/"
    assert view.name == "index"
    assert set(view.methods) == {"HEAD", "GET", "POST"}


def test_route_calls_guards(test_client_factory: TestClientFactory) -> None:
    spy = mock.MagicMock()

    def malaysian_guard(request: Request) -> None:
        spy()

    @route("/", methods=["get", "post"], name="index", guards=[malaysian_guard])
    async def view(request: Request) -> JSONResponse:
        return JSONResponse({})

    client = test_client_factory(routes=[view])
    client.get("/")
    spy.assert_called_once()


def test_injects_path_params(test_client_factory: TestClientFactory) -> None:
    @route("/users/{id}")
    async def view(id: int) -> PlainTextResponse:
        return PlainTextResponse(id)

    client = test_client_factory(routes=[view])
    response = client.get("/users/1")
    assert response.status_code == 200
    assert response.text == "1"


def test_custom_request_class(test_client_factory: TestClientFactory) -> None:
    class CustomRequest(Request):
        @property
        def request_type(self) -> str:
            return "custom"

    @route("/")
    async def view(request: CustomRequest) -> JSONResponse:
        return JSONResponse({"class": request.__class__.__name__, "type": request.request_type})

    client = test_client_factory(routes=[view])
    response = client.get("/")
    assert response.json() == {"class": "CustomRequest", "type": "custom"}
