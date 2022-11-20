from starlette.middleware.sessions import SessionMiddleware
from starlette_flash import flash

from kupala.middleware import Middleware
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


def test_redirect_to_path_with_flash_message(test_client_factory: TestClientFactory) -> None:
    @route("/")
    def view(request: Request) -> RedirectResponse:
        return RedirectResponse.to_path_name(request, "about", flash_message="Saved.", flash_category="success")

    @route("/about/", name="about")
    def about_view(request: Request) -> JSONResponse:
        messages = flash(request).all()
        return JSONResponse(messages)

    client = test_client_factory(
        routes=[view, about_view],
        middleware=[
            Middleware(SessionMiddleware, secret_key="key", max_age=80000),
        ],
    )
    response = client.get("/", allow_redirects=True)
    assert response.status_code == 200
    assert response.json() == [{"category": "success", "message": "Saved."}]


def test_redirect_to_url(test_client_factory: TestClientFactory, routes: Routes) -> None:
    @route("/")
    def view(request: Request) -> RedirectResponse:
        return RedirectResponse.to_url(request, "/about", flash_message="Saved.", flash_category="success")

    @route("/about")
    def about_view(request: Request) -> JSONResponse:
        messages = flash(request).all()
        return JSONResponse(messages)

    client = test_client_factory(
        routes=[view, about_view],
        middleware=[
            Middleware(SessionMiddleware, secret_key="key", max_age=80000),
        ],
    )
    response = client.get("/", allow_redirects=True)
    assert response.status_code == 200
    assert response.json() == [{"category": "success", "message": "Saved."}]


def test_redirect_to_url_with_flash(test_client_factory: TestClientFactory, routes: Routes) -> None:
    @route("/")
    def view(request: Request) -> RedirectResponse:
        return RedirectResponse.to_url(request, "/about", flash_message="Saved.", flash_category="success")

    @route("/about")
    def about_view(request: Request) -> JSONResponse:
        messages = flash(request).all()
        return JSONResponse(messages)

    client = test_client_factory(
        routes=[view, about_view],
        middleware=[
            Middleware(SessionMiddleware, secret_key="key", max_age=80000),
        ],
    )
    response = client.get("/", allow_redirects=True)
    assert response.status_code == 200
    assert response.json() == [{"category": "success", "message": "Saved."}]
