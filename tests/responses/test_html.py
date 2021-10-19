from kupala.application import Kupala
from kupala.requests import Request
from kupala.responses import HTMLResponse
from kupala.testclient import TestClient


def test_html() -> None:
    def view(request: Request) -> HTMLResponse:
        return HTMLResponse('<b>html text</b>')

    app = Kupala()
    app.routes.get('/', view)

    client = TestClient(app)
    response = client.get('/')
    assert response.headers['content-type'] == 'text/html; charset=utf-8'
    assert response.text == '<b>html text</b>'
