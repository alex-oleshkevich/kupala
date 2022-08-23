import typing
from imia import LoginState, UserToken
from starlette.types import ASGIApp, Receive, Scope, Send

from kupala.http.middleware.timezone import TimezoneMiddleware
from kupala.http.requests import Request
from kupala.http.responses import JSONResponse
from kupala.testclient import TestClient


async def app(scope: Scope, receive: Receive, send: Send) -> None:
    request = Request(scope, receive, send)
    await JSONResponse(str(request.state.timezone))(scope, receive, send)


class _User:
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


def test_timezone_middleware_detects_tz_from_user() -> None:
    client = TestClient(ForceAuthentication(TimezoneMiddleware(app), timezone="Europe/Minsk"))
    assert client.get("/").json() == "Europe/Minsk"


def test_timezone_middleware_user_supplies_no_language() -> None:
    client = TestClient(ForceAuthentication(TimezoneMiddleware(app), timezone=None))
    assert client.get("/").json() == "UTC"


def test_timezone_middleware_fallback_language() -> None:
    client = TestClient(TimezoneMiddleware(app, fallback="Europe/Warsaw"))
    assert client.get("/").json() == "Europe/Warsaw"


def test_timezone_middleware_use_custom_detector() -> None:
    def detector(request: Request) -> str | None:
        return "Europe/Kiev"

    client = TestClient(TimezoneMiddleware(app, timezone_detector=detector))
    assert client.get("/").json() == "Europe/Kiev"


def test_timezone_middleware_custom_detector_returns_no_locale() -> None:
    def detector(request: Request) -> str | None:
        return None

    client = TestClient(TimezoneMiddleware(app, timezone_detector=detector))
    assert client.get("/").json() == "UTC"
