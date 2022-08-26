from kupala.http import route
from kupala.http.requests import Request
from kupala.http.responses import GoBackResponse, Response
from tests.conftest import TestClientFactory


def test_go_back_response(test_client_factory: TestClientFactory) -> None:
    @route("/")
    def view(request: Request) -> Response:
        return GoBackResponse()

    client = test_client_factory(routes=[view])
    res = client.get("/", headers={"referer": "http://testserver/somepage"}, allow_redirects=False)
    assert res.status_code == 302
    assert res.headers["location"] == "http://testserver/somepage"
