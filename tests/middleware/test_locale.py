import typing
from babel.core import Locale
from imia import LoginState, UserToken
from starlette.types import ASGIApp, Receive, Scope, Send

from kupala.application import Kupala
from kupala.authentication import BaseUser
from kupala.http.middleware import LocaleMiddleware, Middleware
from kupala.http.requests import Request
from kupala.http.responses import JSONResponse
from kupala.http.routing import Route
from kupala.testclient import TestClient


def view(request: Request) -> JSONResponse:
    return JSONResponse([request.locale.language, request.locale.territory])


def test_locale_middleware_detects_locale_from_query() -> None:
    app = Kupala(
        routes=[Route('/', view)],
        middleware=[Middleware(LocaleMiddleware, languages=['be_BY'])],
    )
    client = TestClient(app)
    assert client.get('/?lang=be_BY').json() == ['be', 'BY']


def test_locale_middleware_detects_locale_from_query_using_custom_query_param() -> None:
    app = Kupala(
        routes=[Route('/', view)],
        middleware=[Middleware(LocaleMiddleware, query_param_name='locale', languages=['be_BY'])],
    )
    client = TestClient(app)
    assert client.get('/?locale=be_BY').json() == ['be', 'BY']


def test_locale_middleware_detects_locale_from_cookie() -> None:
    app = Kupala(
        routes=[Route('/', view)],
        middleware=[Middleware(LocaleMiddleware, languages=['be_BY'])],
    )
    client = TestClient(app)
    assert client.get('/', cookies={'language': 'be_BY'}).json() == ['be', 'BY']


def test_locale_middleware_detects_locale_from_cookie_using_custom_name() -> None:
    app = Kupala(
        routes=[Route('/', view)],
        middleware=[Middleware(LocaleMiddleware, cookie_name='lang', languages=['be_BY'])],
    )
    client = TestClient(app)
    assert client.get('/', cookies={'lang': 'be_BY'}).json() == ['be', 'BY']


def test_locale_middleware_detects_locale_from_header() -> None:
    app = Kupala(
        routes=[Route('/', view)],
        middleware=[Middleware(LocaleMiddleware, languages=['be_BY'])],
    )
    client = TestClient(app)
    assert client.get(
        '/', headers={'accept-language': 'en-US,en;q=0.9,ru-BY;q=0.8,ru;q=0.7,be-BY;q=0.6,be;q=0.5,pl;q=0.4,de;q=0.3'}
    ).json() == ['be', 'BY']


def test_locale_middleware_detects_locale_from_header_with_wildcard() -> None:
    app = Kupala(
        routes=[Route('/', view)],
        middleware=[Middleware(LocaleMiddleware, languages=['be_BY'])],
    )
    client = TestClient(app)
    assert client.get('/', headers={'accept-language': '*'}).json() == ['en', 'US']


def test_locale_middleware_supports_language_shortcuts() -> None:
    app = Kupala(
        routes=[Route('/', view)],
        middleware=[Middleware(LocaleMiddleware, languages=['be'])],
    )
    client = TestClient(app)
    assert client.get('/?lang=be_BY').json() == ['be', None]


class _User(BaseUser):
    def __init__(self, language: str | None) -> None:
        self.language = language

    def get_id(self) -> typing.Any:
        pass

    def get_display_name(self) -> str:
        pass

    def get_scopes(self) -> list[str]:
        pass

    def get_hashed_password(self) -> str:
        pass

    def get_preferred_language(self) -> str | None:
        return self.language


class ForceAuthentication:
    def __init__(self, app: ASGIApp, language: str | None) -> None:
        self.app = app
        self.language = language

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        scope['auth'] = UserToken(user=_User(language=self.language), state=LoginState.FRESH)
        await self.app(scope, receive, send)


def test_locale_middleware_detects_locale_from_user() -> None:
    app = Kupala(
        routes=[Route('/', view)],
        middleware=[
            Middleware(ForceAuthentication, language='be_BY'),
            Middleware(LocaleMiddleware, languages=['be_BY']),
        ],
    )
    client = TestClient(app)
    assert client.get('/').json() == ['be', 'BY']


def test_locale_middleware_user_supplies_no_language() -> None:
    app = Kupala(
        routes=[Route('/', view)],
        middleware=[Middleware(ForceAuthentication, language=None), Middleware(LocaleMiddleware, languages=['be_BY'])],
    )
    client = TestClient(app)
    assert client.get('/').json() == ['en', 'US']


def test_locale_middleware_finds_variant() -> None:
    """If there is no locale exactly matching the requested, try to find
    alternate variant that may satisfy the client."""
    app = Kupala(
        routes=[Route('/', view)],
        middleware=[Middleware(LocaleMiddleware, languages=['ru_BY'])],
    )
    client = TestClient(app)
    assert client.get('/?lang=ru_RU').json() == ['ru', 'BY']


def test_locale_middleware_fallback_language() -> None:
    """If there is no locale exactly matching the requested, try to find
    alternate variant that may satisfy the client."""
    app = Kupala(
        routes=[Route('/', view)],
        middleware=[Middleware(LocaleMiddleware, languages=['be_BY'], default_locale='pl_PL')],
    )
    client = TestClient(app)
    assert client.get('/?lang=ru_RU').json() == ['pl', 'PL']


def test_locale_middleware_use_custom_detector() -> None:
    def detector(request: Request) -> Locale | None:
        return Locale.parse('be_BY')

    app = Kupala(
        routes=[Route('/', view)],
        middleware=[Middleware(LocaleMiddleware, languages=['be_BY'], locale_detector=detector)],
    )
    client = TestClient(app)
    assert client.get('/').json() == ['be', 'BY']


def test_locale_middleware_custom_detector_returns_no_locale() -> None:
    def detector(request: Request) -> Locale | None:
        return None

    app = Kupala(
        routes=[Route('/', view)],
        middleware=[Middleware(LocaleMiddleware, languages=['be_BY'], locale_detector=detector)],
    )
    client = TestClient(app)
    assert client.get('/').json() == ['en', 'US']
