import typing
from imia import LoginState, UserToken
from pytz import BaseTzInfo
from starlette.types import ASGIApp, Receive, Scope, Send

from kupala.authentication import BaseUser
from kupala.http.middleware import Middleware
from kupala.http.middleware.timezone import TimezoneMiddleware
from kupala.http.requests import Request
from kupala.http.responses import JSONResponse
from kupala.http.routing import Route, Routes
from kupala.testclient import TestClient
from tests.conftest import TestAppFactory


def view(request: Request) -> JSONResponse:
    return JSONResponse(str(request.state.timezone))


class _User(BaseUser):
    def __init__(self, timezone: str | None) -> None:
        self.timezone = timezone

    def get_id(self) -> typing.Any:
        pass

    def get_display_name(self) -> str:
        pass

    def get_scopes(self) -> list[str]:
        pass

    def get_hashed_password(self) -> str:
        pass

    def get_timezone(self) -> str | None:
        return self.timezone


class ForceAuthentication:
    def __init__(self, app: ASGIApp, timezone: str | None) -> None:
        self.app = app
        self.timezone = timezone

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        scope["auth"] = UserToken(user=_User(timezone=self.timezone), state=LoginState.FRESH)
        await self.app(scope, receive, send)


def test_timezone_middleware_detects_tz_from_user(test_app_factory: TestAppFactory) -> None:
    app = test_app_factory(
        routes=Routes([Route("/", view)]),
        middleware=[
            Middleware(ForceAuthentication, timezone="Europe/Minsk"),
            Middleware(TimezoneMiddleware),
        ],
    )
    client = TestClient(app)
    assert client.get("/").json() == "Europe/Minsk"


def test_timezone_middleware_user_supplies_no_language(test_app_factory: TestAppFactory) -> None:
    app = test_app_factory(
        routes=Routes([Route("/", view)]),
        middleware=[Middleware(ForceAuthentication, timezone=None), Middleware(TimezoneMiddleware)],
    )
    client = TestClient(app)
    assert client.get("/").json() == "UTC"


def test_timezone_middleware_fallback_language(test_app_factory: TestAppFactory) -> None:
    app = test_app_factory(
        routes=Routes([Route("/", view)]),
        middleware=[Middleware(TimezoneMiddleware, fallback="Europe/Warsaw")],
    )
    client = TestClient(app)
    assert client.get("/").json() == "Europe/Warsaw"


def test_timezone_middleware_use_custom_detector(test_app_factory: TestAppFactory) -> None:
    def detector(request: Request) -> str | BaseTzInfo | None:
        return "Europe/Kiev"

    app = test_app_factory(
        routes=Routes([Route("/", view)]),
        middleware=[Middleware(TimezoneMiddleware, timezone_detector=detector)],
    )
    client = TestClient(app)
    assert client.get("/").json() == "Europe/Kiev"


def test_timezone_middleware_custom_detector_returns_no_locale(test_app_factory: TestAppFactory) -> None:
    def detector(request: Request) -> str | BaseTzInfo | None:
        return None

    app = test_app_factory(
        routes=Routes([Route("/", view)]),
        middleware=[Middleware(TimezoneMiddleware, timezone_detector=detector)],
    )
    client = TestClient(app)
    assert client.get("/").json() == "UTC"
