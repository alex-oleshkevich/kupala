from kupala.requests import Request
from kupala.responses import JSONResponse, RedirectResponse
from kupala.routing import Routes, route
from tests.conftest import TestClientFactory


def test_redirect_to_path_name(test_client_factory: TestClientFactory) -> None:
    @route("/")
    def view(request: Request) -> RedirectResponse:
        return RedirectResponse.to_path_name(request, path_name="about")

    @route("/about", name="about")
    def about_view() -> JSONResponse:
        return JSONResponse({})

    client = test_client_factory(routes=[view, about_view])
    response = client.get("/", allow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "/about"


def test_redirect_to_path_name_with_path_params(test_client_factory: TestClientFactory) -> None:
    @route("/")
    def view(request: Request) -> RedirectResponse:
        return RedirectResponse.to_path_name(request, path_name="about", path_params={"id": 42})

    @route("/about/{id}", name="about")
    def about_view() -> JSONResponse:
        return JSONResponse({})

    client = test_client_factory(routes=[view, about_view])
    response = client.get("/", allow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "/about/42"


def test_redirect_to_url(test_client_factory: TestClientFactory, routes: Routes) -> None:
    @route("/")
    def view(request: Request) -> RedirectResponse:
        return RedirectResponse.to_url("/about")

    @route("/about")
    def about_view(request: Request) -> JSONResponse:
        return JSONResponse("ok")

    client = test_client_factory(
        routes=[view, about_view],
    )
    response = client.get("/", allow_redirects=True)
    assert response.status_code == 200
    assert response.json() == "ok"
