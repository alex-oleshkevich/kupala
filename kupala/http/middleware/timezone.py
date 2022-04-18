import typing
from starlette.types import ASGIApp, Receive, Scope, Send

from kupala.http import Request
from kupala.i18n.protocols import HasTimezone
from kupala.i18n.timezone import switch_timezone


def _get_timezone_from_user(request: Request) -> str | None:
    tz_provider = typing.cast(HasTimezone, request.user)
    if hasattr(tz_provider, 'get_timezone'):
        return getattr(tz_provider, 'get_timezone')()
    return None


class TimezoneMiddleware:
    def __init__(
        self,
        app: ASGIApp,
        fallback: str = 'UTC',
        timezone_detector: typing.Callable[[Request], str | None] = None,
    ) -> None:
        self.app = app
        self.fallback = fallback
        self.timezone_detector = timezone_detector or self.detect_timezone

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        request = Request(scope, receive, send)
        tz = self.timezone_detector(request) or self.fallback
        with switch_timezone(tz):
            request.state.timezone = tz
            await self.app(scope, receive, send)

    def detect_timezone(self, request: Request) -> str | None:
        if tz := _get_timezone_from_user(request):
            return tz
        return None
