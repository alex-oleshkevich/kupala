from kupala.http import Routes
from kupala.http.requests import Request
from kupala.http.responses import GoBackResponse, Response
from tests.conftest import TestClientFactory


def test_go_back_response(test_client_factory: TestClientFactory, routes: Routes) -> None:
    def view(request: Request) -> Response:
        return GoBackResponse(request)

    routes.add('/', view)
    client = test_client_factory(routes=routes)
    res = client.get('/', headers={'referer': 'http://testserver/somepage'}, allow_redirects=False)
    assert res.status_code == 302
    assert res.headers['location'] == 'http://testserver/somepage'
