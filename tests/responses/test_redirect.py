import pytest
from starlette.middleware.sessions import SessionMiddleware

from kupala.http import Routes, route
from kupala.http.middleware import Middleware
from kupala.http.middleware.flash_messages import FlashMessagesMiddleware, flash
from kupala.http.requests import Request
from kupala.http.responses import JSONResponse, RedirectResponse
from tests.conftest import TestClientFactory

REDIRECT_INPUT_DATA_SESSION_KEY = "_form_old_input"


def test_redirect(test_client_factory: TestClientFactory) -> None:
    @route("/")
    def view() -> RedirectResponse:
        return RedirectResponse("/about")

    client = test_client_factory(routes=[view])

    response = client.get("/", allow_redirects=False)
    assert response.headers["location"] == "/about"


def test_redirect_requires_url_or_path_name(test_client_factory: TestClientFactory) -> None:
    @route("/")
    def view() -> RedirectResponse:
        return RedirectResponse()

    client = test_client_factory(routes=[view])

    with pytest.raises(AssertionError) as ex:
        client.get("/")
    assert str(ex.value) == 'Either "url" or "path_name" argument must be passed.'


def test_redirect_to_path_name(test_client_factory: TestClientFactory) -> None:
    @route("/")
    def view() -> RedirectResponse:
        return RedirectResponse(path_name="about")

    @route("/about", name="about")
    def about_view() -> JSONResponse:
        return JSONResponse({})

    client = test_client_factory(routes=[view, about_view])
    response = client.get("/", allow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "/about"


def test_redirect_to_path_name_with_path_params(test_client_factory: TestClientFactory) -> None:
    @route("/")
    def view() -> RedirectResponse:
        return RedirectResponse(path_name="about", path_params={"id": 42})

    @route("/about/{id}", name="about")
    def about_view() -> JSONResponse:
        return JSONResponse({})

    client = test_client_factory(routes=[view, about_view])
    response = client.get("/", allow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "/about/42"


def test_redirect_with_flash_message(test_client_factory: TestClientFactory) -> None:
    @route("/")
    def view(request: Request) -> RedirectResponse:
        return RedirectResponse("/about", flash_message="Saved.", flash_category="success")

    @route("/about/")
    def about_view(request: Request) -> JSONResponse:
        messages = flash(request).all()
        return JSONResponse(messages)

    client = test_client_factory(
        routes=[view, about_view],
        middleware=[
            Middleware(SessionMiddleware, secret_key="key", max_age=80000),
            Middleware(FlashMessagesMiddleware, storage="session"),
        ],
    )
    response = client.get("/", allow_redirects=True)
    assert response.status_code == 200
    assert response.json() == [{"category": "success", "message": "Saved."}]


def test_redirect_with_flash_message_via_method(test_client_factory: TestClientFactory) -> None:
    @route("/")
    def view() -> RedirectResponse:
        return RedirectResponse("/about").flash("Saved.")

    @route("/about")
    def about_view(request: Request) -> JSONResponse:
        messages = flash(request).all()
        return JSONResponse(messages)

    client = test_client_factory(
        routes=[view, about_view],
        middleware=[
            Middleware(SessionMiddleware, secret_key="key", max_age=80000),
            Middleware(FlashMessagesMiddleware, storage="session"),
        ],
    )
    response = client.get("/", allow_redirects=True)
    assert response.status_code == 200
    assert response.json() == [{"category": "success", "message": "Saved."}]


def test_redirect_with_success(test_client_factory: TestClientFactory, routes: Routes) -> None:
    @route("/")
    def view() -> RedirectResponse:
        return RedirectResponse("/about").with_success("Saved.")

    @route("/about")
    def about_view(request: Request) -> JSONResponse:
        messages = flash(request).all()
        return JSONResponse(messages)

    client = test_client_factory(
        routes=[view, about_view],
        middleware=[
            Middleware(SessionMiddleware, secret_key="key", max_age=80000),
            Middleware(FlashMessagesMiddleware, storage="session"),
        ],
    )
    response = client.get("/", allow_redirects=True)
    assert response.status_code == 200
    assert response.json() == [{"category": "success", "message": "Saved."}]


def test_redirect_with_error(test_client_factory: TestClientFactory, routes: Routes) -> None:
    @route("/")
    def view() -> RedirectResponse:
        return RedirectResponse("/about").with_error("Error.")

    @route("/about")
    def about_view(request: Request) -> JSONResponse:
        messages = flash(request).all()
        return JSONResponse(messages)

    client = test_client_factory(
        routes=[view, about_view],
        middleware=[
            Middleware(SessionMiddleware, secret_key="key", max_age=80000),
            Middleware(FlashMessagesMiddleware, storage="session"),
        ],
    )
    response = client.get("/", allow_redirects=True)
    assert response.status_code == 200
    assert response.json() == [{"category": "error", "message": "Error."}]
