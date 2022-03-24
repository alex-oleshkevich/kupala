import contextvars as cv
import datetime
import typing
from babel.core import Locale
from babel.dates import get_timezone as babel_get_timezone
from babel.util import UTC
from contextlib import contextmanager
from pytz.tzinfo import BaseTzInfo
from typing import Generator

from kupala.http.requests import Request
from kupala.http.responses import Response

_current_locale: cv.ContextVar[Locale] = cv.ContextVar("current_locale", default=Locale.parse("en_US"))
_current_language: cv.ContextVar[str] = cv.ContextVar("current_language", default="en")
_current_timezone: cv.ContextVar[BaseTzInfo] = cv.ContextVar("current_timezone", default=UTC)


def get_locale() -> Locale:
    """Return currently active locale."""
    return _current_locale.get()


def set_locale(locale: Locale | str) -> None:
    """Set active locale."""
    if isinstance(locale, str):
        locale = Locale.parse(locale)
    _current_locale.set(locale)


@contextmanager
def switch_locale(locale: str) -> Generator[None, None, None]:
    old_locale = get_locale()
    set_locale(locale)
    yield
    set_locale(old_locale)


def get_language() -> str:
    """Get current language."""
    return get_locale().language


def get_timezone() -> BaseTzInfo:
    """Return currently active timezone."""
    return _current_timezone.get()


def set_timezone(timezone: str | BaseTzInfo) -> None:
    """Set active timezone."""
    if isinstance(timezone, str):
        timezone = babel_get_timezone(timezone)
    assert not isinstance(timezone, str)
    _current_timezone.set(timezone)


@contextmanager
def switch_timezone(tz: str) -> Generator[None, None, None]:
    old_timezone = get_timezone()
    set_timezone(tz)
    yield
    set_timezone(old_timezone)


def to_user_timezone(dt: datetime.datetime) -> datetime.datetime:
    """Convert datetime instance into current timezone."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    tzinfo = get_timezone()
    return dt.astimezone(tzinfo)


def to_utc(dt: datetime.datetime) -> datetime.datetime:
    """Convert datetime instance to UTC and drop tzinfo (creates a naive
    datetime object)."""
    if dt.tzinfo is None:
        dt = get_timezone().localize(dt)
    return dt.astimezone(UTC).replace(tzinfo=None)


_R = typing.TypeVar('_R', bound=Response)


def remember_current_language(request: Request, response: _R) -> _R:
    """Remember current locale in cookie."""
    response.set_cookie(request.scope.get('i18n.cookie_name', 'language'), str(request.locale))
    return response
