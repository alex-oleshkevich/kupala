from kupala.http import route
from kupala.http.requests import Request
from kupala.http.responses import HTMLResponse
from tests.conftest import TestClientFactory


def test_html(test_client_factory: TestClientFactory) -> None:
    @route("/")
    def view(request: Request) -> HTMLResponse:
        return HTMLResponse("<b>html text</b>")

    client = test_client_factory(routes=[view])
    response = client.get("/")
    assert response.headers["content-type"] == "text/html; charset=utf-8"
    assert response.text == "<b>html text</b>"
