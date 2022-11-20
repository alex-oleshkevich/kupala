from kupala.responses import Response
from kupala.routing import Request, route
from tests.conftest import TestClientFactory


def test_route(test_client_factory: TestClientFactory) -> None:
    @route("/")
    def index(_: Request) -> Response:
        return Response("ok")

    client = test_client_factory(routes=[index])
    response = client.get("/")
    assert response.status_code == 200
    assert response.text == "ok"


def test_injects_path_params(test_client_factory: TestClientFactory) -> None:
    @route("/users/{id}")
    async def view(request: Request, id: str) -> Response:
        return Response(id)

    client = test_client_factory(routes=[view])
    response = client.get("/users/1")
    assert response.status_code == 200
    assert response.text == "1"
