import contextvars as cv
import typing
from babel.core import Locale
from contextlib import contextmanager
from typing import Generator

from kupala.http.requests import Request
from kupala.http.responses import Response

_current_locale: cv.ContextVar[Locale] = cv.ContextVar("current_locale", default=Locale.parse("en_US"))
_current_language: cv.ContextVar[str] = cv.ContextVar("current_language", default="en")


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


_R = typing.TypeVar('_R', bound=Response)


def remember_current_language(request: Request, response: _R) -> _R:
    """Remember current locale in cookie."""
    response.set_cookie(request.scope.get('i18n.cookie_name', 'language'), str(request.locale))
    return response
