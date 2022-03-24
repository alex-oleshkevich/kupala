from kupala.application import Kupala
from kupala.http.requests import Request
from kupala.http.responses import EmptyResponse
from kupala.testclient import TestClient


def test_empty() -> None:
    def view(request: Request) -> EmptyResponse:
        return EmptyResponse()

    app = Kupala()
    app.routes.add('/', view)

    client = TestClient(app)
    response = client.get('/')
    assert response.status_code == 204
