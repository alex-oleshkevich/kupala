import contextvars as cv
from babel import Locale
from contextlib import contextmanager
from typing import Generator

_current_locale: cv.ContextVar[Locale] = cv.ContextVar("current_locale", default=Locale.parse("en_US"))


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
