from kupala.http import Routes
from kupala.http.requests import Request
from kupala.http.responses import PlainTextResponse
from tests.conftest import TestClientFactory


def test_plain_text_response(test_client_factory: TestClientFactory, routes: Routes) -> None:
    def view(request: Request) -> PlainTextResponse:
        return PlainTextResponse("plain text response")

    routes.add("/", view)
    client = test_client_factory(routes=routes)
    response = client.get("/")
    assert response.headers["content-type"] == "text/plain; charset=utf-8"
    assert response.text == "plain text response"
