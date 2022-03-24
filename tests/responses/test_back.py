from kupala.application import Kupala
from kupala.http.requests import Request
from kupala.http.responses import GoBackResponse, Response
from kupala.testclient import TestClient


def test_go_back_response() -> None:
    def view(request: Request) -> Response:
        return GoBackResponse(request)

    app = Kupala()
    app.routes.add('/', view)

    client = TestClient(app)
    res = client.get('/', headers={'referer': 'http://testserver/somepage'}, allow_redirects=False)
    assert res.status_code == 302
    assert res.headers['location'] == 'http://testserver/somepage'
