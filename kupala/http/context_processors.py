import typing

from kupala.http.middleware.csrf import get_csrf_input, get_csrf_token
from kupala.http.middleware.flash_messages import flash
from kupala.http.requests import Request


def standard_processors(request: Request) -> dict[str, typing.Any]:
    return {
        'app': request.app,
        'request': request,
        'url': request.url_for,
        'static': request.static_url,
        'flash_messages': flash(request),
        'csrf_token': get_csrf_token(request),
        'csrf_input': get_csrf_input(request),
    }
