from kupala.http import Routes
from kupala.http.requests import Request
from kupala.http.responses import HTMLResponse
from tests.conftest import TestClientFactory


def test_html(test_client_factory: TestClientFactory, routes: Routes) -> None:
    def view(request: Request) -> HTMLResponse:
        return HTMLResponse('<b>html text</b>')

    routes.add('/', view)
    client = test_client_factory(routes=routes)
    response = client.get('/')
    assert response.headers['content-type'] == 'text/html; charset=utf-8'
    assert response.text == '<b>html text</b>'
