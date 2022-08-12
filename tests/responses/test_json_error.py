from kupala.http import Routes
from kupala.http.requests import Request
from kupala.http.responses import JSONErrorResponse, JSONResponse
from tests.conftest import TestClientFactory


def test_json_error(test_client_factory: TestClientFactory, routes: Routes) -> None:
    def view(request: Request) -> JSONResponse:
        return JSONErrorResponse(message="Error", errors={"field": ["error1", "error2"]}, code="errcode")

    routes.add("/", view)
    client = test_client_factory(routes=routes)
    assert client.get("/").json() == {
        "message": "Error",
        "errors": {"field": ["error1", "error2"]},
        "code": "errcode",
    }
