import typing

from kupala.http.middleware.flash_messages import flash
from kupala.http.requests import Request


def standard_processor(request: Request) -> dict[str, typing.Any]:
    return {
        'app': request.app,
        'request': request,
        'url': request.url_for,
        'static': request.static_url,
        'flash_messages': flash(request),
        'form_errors': request.form_errors,
        'old_input': request.old_input,
    }
