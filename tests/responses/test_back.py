from kupala.requests import Request
from kupala.responses import Response, redirect_back
from kupala.routing import route
from tests.conftest import ClientFactory


def test_go_back_response(test_client_factory: ClientFactory) -> None:
    @route("/")
    def view(request: Request) -> Response:
        return redirect_back(request)

    client = test_client_factory(routes=[view])
    res = client.get("/", headers={"referer": "http://testserver/somepage"}, follow_redirects=False)
    assert res.status_code == 302
    assert res.headers["location"] == "http://testserver/somepage"


def test_go_back_response_without_refererer(test_client_factory: ClientFactory) -> None:
    @route("/")
    def view(request: Request) -> Response:
        return redirect_back(request)

    client = test_client_factory(routes=[view])
    res = client.get("/", follow_redirects=False)
    assert res.status_code == 302
    assert res.headers["location"] == "/"


def test_go_back_response_with_invalid_refererer(test_client_factory: ClientFactory) -> None:
    @route("/")
    def view(request: Request) -> Response:
        return redirect_back(request)

    client = test_client_factory(routes=[view])
    res = client.get("/", headers={"referer": "http://example.com"}, follow_redirects=False)
    assert res.status_code == 302
    assert res.headers["location"] == "/"
