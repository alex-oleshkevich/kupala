import datetime
from babel.core import Locale
from babel.dates import get_timezone as babel_get_timezone

from kupala.application import Kupala
from kupala.http.middleware import LocaleMiddleware
from kupala.http.requests import Request
from kupala.http.responses import JSONResponse
from kupala.i18n.helpers import (
    get_language,
    get_locale,
    get_timezone,
    remember_current_language,
    set_locale,
    set_timezone,
    switch_locale,
    switch_timezone,
    to_user_timezone,
    to_utc,
)
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


def test_set_get_timezone() -> None:
    set_timezone('Europe/Warsaw')
    set_timezone('Europe/Minsk')
    assert str(get_timezone()) == 'Europe/Minsk'

    tz = babel_get_timezone('Europe/Minsk')
    set_timezone(tz)
    assert get_timezone() == tz


def test_switch_timezone() -> None:
    set_timezone('Europe/Warsaw')
    with switch_timezone('Europe/Minsk'):
        assert str(get_timezone()) == 'Europe/Minsk'
    assert str(get_timezone()) == 'Europe/Warsaw'


def test_to_user_timezone() -> None:
    """
    Europe/Minsk is +3:00.

    Naive dates considered to be in UTC.
    """
    with switch_timezone('Europe/Minsk'):
        naive_dt = datetime.datetime(2022, 12, 25, 12, 30, 59)
        assert to_user_timezone(naive_dt).isoformat() == '2022-12-25T15:30:59+03:00'

        aware_dt = datetime.datetime(2022, 12, 25, 12, 30, 59, tzinfo=babel_get_timezone('CET'))
        assert to_user_timezone(aware_dt).isoformat() == '2022-12-25T14:30:59+03:00'


def test_to_utc() -> None:
    """Naive time will be assigned current timezone (Europe/Minsk) and then
    converted to UTC."""
    with switch_timezone('Europe/Minsk'):
        naive_dt = datetime.datetime(2022, 12, 25, 12, 30, 59)
        assert to_utc(naive_dt).isoformat() == '2022-12-25T09:30:59'

        aware_dt = datetime.datetime(2022, 12, 25, 12, 30, 59, tzinfo=babel_get_timezone('CET'))
        assert to_utc(aware_dt).isoformat() == '2022-12-25T11:30:59'


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
