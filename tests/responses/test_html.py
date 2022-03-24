from kupala.application import Kupala
from kupala.http.requests import Request
from kupala.http.responses import HTMLResponse
from kupala.testclient import TestClient


def test_html() -> None:
    def view(request: Request) -> HTMLResponse:
        return HTMLResponse('<b>html text</b>')

    app = Kupala()
    app.routes.add('/', view)

    client = TestClient(app)
    response = client.get('/')
    assert response.headers['content-type'] == 'text/html; charset=utf-8'
    assert response.text == '<b>html text</b>'
