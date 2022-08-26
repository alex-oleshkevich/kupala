from kupala.http import route
from kupala.http.requests import Request
from kupala.http.responses import PlainTextResponse
from tests.conftest import TestClientFactory


def test_plain_text_response(test_client_factory: TestClientFactory) -> None:
    @route("/")
    def view(request: Request) -> PlainTextResponse:
        return PlainTextResponse("plain text response")

    client = test_client_factory(routes=[view])
    response = client.get("/")
    assert response.headers["content-type"] == "text/plain; charset=utf-8"
    assert response.text == "plain text response"
