from kupala.requests import Request
from kupala.responses import EmptyResponse
from kupala.routing import route
from tests.conftest import TestClientFactory


def test_empty(test_client_factory: TestClientFactory) -> None:
    @route("/")
    def view(request: Request) -> EmptyResponse:
        return EmptyResponse()

    client = test_client_factory(routes=[view])
    response = client.get("/")
    assert response.status_code == 204
