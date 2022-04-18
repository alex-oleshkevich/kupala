import contextvars as cv
import typing

from kupala.http.requests import Request
from kupala.http.responses import Response
from kupala.i18n.locale import get_locale

_current_language: cv.ContextVar[str] = cv.ContextVar("current_language", default="en")


def get_language() -> str:
    """Get current language."""
    return get_locale().language


_R = typing.TypeVar('_R', bound=Response)


def remember_current_language(request: Request, response: _R) -> _R:
    """Remember current locale in cookie."""
    response.set_cookie(request.scope.get('i18n.cookie_name', 'language'), str(request.locale))
    return response
