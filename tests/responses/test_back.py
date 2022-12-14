from kupala.requests import Request
from kupala.responses import Response, redirect_back
from kupala.routing import route
from tests.conftest import TestClientFactory


def test_go_back_response(test_client_factory: TestClientFactory) -> None:
    @route("/")
    def view(request: Request) -> Response:
        return redirect_back(request)

    client = test_client_factory(routes=[view])
    res = client.get("/", headers={"referer": "http://testserver/somepage"}, allow_redirects=False)
    assert res.status_code == 302
    assert res.headers["location"] == "http://testserver/somepage"
