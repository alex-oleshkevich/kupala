from babel.core import Locale

from kupala.http import route
from kupala.http.middleware import LocaleMiddleware, Middleware
from kupala.http.requests import Request
from kupala.http.responses import JSONResponse
from kupala.i18n import get_locale, set_locale, switch_locale
from kupala.i18n.language import get_language, remember_current_language
from kupala.testclient import TestClient
from tests.conftest import TestAppFactory


def test_set_get_locale() -> None:
    set_locale("en_US")
    set_locale("be_BY")
    assert str(get_locale()) == "be_BY"

    locale = Locale("be_BY")
    set_locale(locale)
    assert get_locale() == locale


def test_temporary_switch_locale() -> None:
    set_locale("en_US")
    with switch_locale("be_BY"):
        assert str(get_locale()) == "be_BY"
    assert str(get_locale()) == "en_US"


def test_get_language() -> None:
    set_locale("be_BY")
    assert get_language() == "be"


def test_remember_language(test_app_factory: TestAppFactory) -> None:
    @route("/")
    def view(request: Request) -> JSONResponse:
        response = JSONResponse(request.language)
        return remember_current_language(request, response)

    set_locale("be")
    app = test_app_factory(
        routes=[view],
        middleware=[
            Middleware(LocaleMiddleware, languages=["be", "pl", "en"]),
        ],
    )

    client = TestClient(app)
    response = client.get("/")
    assert response.text == '"en"'

    # select language
    response = client.get("/?lang=be")
    assert response.status_code == 200

    # check language
    response = client.get("/")
    assert response.text == '"be"'
