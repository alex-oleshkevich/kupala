from kupala.http.requests import Request
from kupala.http.responses import JSONResponse, PlainTextResponse
from kupala.http.routing import Routes
from tests.conftest import TestClientFactory


class CustomRequest(Request):
    @property
    def request_type(self) -> str:
        return "custom"


def test_calls_sync_view(test_client_factory: TestClientFactory, routes: Routes) -> None:
    def view() -> PlainTextResponse:
        return PlainTextResponse("ok")

    routes.add("/", view)
    client = test_client_factory(routes=routes)
    response = client.get("/")
    assert response.status_code == 200
    assert response.text == "ok"


def test_calls_async_view(test_client_factory: TestClientFactory, routes: Routes) -> None:
    async def view() -> PlainTextResponse:
        return PlainTextResponse("ok")

    routes.add("/", view)
    client = test_client_factory(routes=routes)
    response = client.get("/")
    assert response.status_code == 200
    assert response.text == "ok"


def test_injects_path_params(test_client_factory: TestClientFactory, routes: Routes) -> None:
    async def view(id: int) -> PlainTextResponse:
        return PlainTextResponse(id)

    routes.add("/users/{id}", view)
    client = test_client_factory(routes=routes)
    response = client.get("/users/1")
    assert response.status_code == 200
    assert response.text == "1"


def test_custom_request_class(test_client_factory: TestClientFactory, routes: Routes) -> None:
    async def view(request: CustomRequest) -> JSONResponse:
        return JSONResponse({"class": request.__class__.__name__, "type": request.request_type})

    routes.add("/", view)
    client = test_client_factory(routes=routes)
    response = client.get("/")
    assert response.json() == {
        "class": "CustomRequest",
        "type": "custom",
    }
