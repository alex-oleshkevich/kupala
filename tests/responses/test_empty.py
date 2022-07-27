from kupala.http import Routes
from kupala.http.requests import Request
from kupala.http.responses import EmptyResponse
from tests.conftest import TestClientFactory


def test_empty(test_client_factory: TestClientFactory, routes: Routes) -> None:
    def view(request: Request) -> EmptyResponse:
        return EmptyResponse()

    routes.add('/', view)
    client = test_client_factory(routes=routes)
    response = client.get('/')
    assert response.status_code == 204
