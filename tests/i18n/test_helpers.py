from babel.core import Locale

from kupala.application import Kupala
from kupala.http.middleware import LocaleMiddleware
from kupala.http.requests import Request
from kupala.http.responses import JSONResponse
from kupala.i18n.helpers import get_language, get_locale, remember_current_language, set_locale, switch_locale
from kupala.testclient import TestClient


def test_set_get_locale() -> None:
    set_locale('en_US')
    set_locale('be_BY')
    assert str(get_locale()) == 'be_BY'

    locale = Locale('be_BY')
    set_locale(locale)
    assert get_locale() == locale


def test_temporary_switch_locale() -> None:
    set_locale('en_US')
    with switch_locale('be_BY'):
        assert str(get_locale()) == 'be_BY'
    assert str(get_locale()) == 'en_US'


def test_get_language() -> None:
    set_locale('be_BY')
    assert get_language() == 'be'


def test_remember_language() -> None:
    def view(request: Request) -> JSONResponse:
        response = JSONResponse(request.language)
        return remember_current_language(request, response)

    set_locale('be')
    app = Kupala()
    app.routes.add('/', view)
    app.middleware.use(LocaleMiddleware, languages=['be', 'pl', 'en'])

    client = TestClient(app)
    response = client.get('/')
    assert response.text == '"en"'

    # select language
    response = client.get('/?lang=be')
    assert response.status_code == 200

    # check language
    response = client.get('/')
    assert response.text == '"be"'
