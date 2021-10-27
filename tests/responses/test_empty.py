from kupala.application import Kupala
from kupala.requests import Request
from kupala.responses import EmptyResponse
from kupala.testclient import TestClient


def test_empty() -> None:
    def view(request: Request) -> EmptyResponse:
        return EmptyResponse()

    app = Kupala()
    app.routes.get('/', view)

    client = TestClient(app)
    response = client.get('/')
    assert response.status_code == 204
