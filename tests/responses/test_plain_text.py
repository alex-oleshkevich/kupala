from kupala.application import Kupala
from kupala.requests import Request
from kupala.responses import PlainTextResponse
from kupala.testclient import TestClient


def test_plain_text_response() -> None:
    def view(request: Request) -> PlainTextResponse:
        return PlainTextResponse('plain text response')

    app = Kupala()
    app.routes.add('/', view)

    client = TestClient(app)
    response = client.get('/')
    assert response.headers['content-type'] == 'text/plain; charset=utf-8'
    assert response.text == 'plain text response'
