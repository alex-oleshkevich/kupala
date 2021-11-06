from kupala.application import Kupala
from kupala.requests import Request
from kupala.responses import GoBackResponse, Response
from kupala.testclient import TestClient


def test_go_back_response() -> None:
    def view(request: Request) -> Response:
        return GoBackResponse(request)

    app = Kupala()
    app.routes.get('/', view)

    client = TestClient(app)
    res = client.get('/', headers={'referer': 'http://testserver/somepage'}, allow_redirects=False)
    assert res.status_code == 302
    assert res.headers['location'] == 'http://testserver/somepage'