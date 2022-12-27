from starlette.responses import Response

from kupala.requests import Request
from kupala.responses import empty_response
from kupala.routing import route
from tests.conftest import ClientFactory


def test_empty(test_client_factory: ClientFactory) -> None:
    @route("/")
    def view(request: Request) -> Response:
        return empty_response()

    client = test_client_factory(routes=[view])
    response = client.get("/")
    assert response.status_code == 204
