import contextvars as cv
import datetime
from babel.dates import get_timezone as babel_get_timezone
from babel.util import UTC
from contextlib import contextmanager
from pytz import BaseTzInfo
from typing import Generator

_current_timezone: cv.ContextVar[BaseTzInfo] = cv.ContextVar("current_timezone", default=UTC)


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
