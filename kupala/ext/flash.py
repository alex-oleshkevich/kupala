import typing

from kupala.application import App, Extension
from kupala.http import Request
from kupala.http.middleware import FlashMessagesMiddleware
from kupala.http.middleware.flash_messages import flash


def _context_processor(request: Request) -> dict[str, typing.Any]:
    return {
        "flash_messages": flash(request),
    }


def use_flash_messages() -> Extension:
    """Enable session support."""

    def extension(app: App) -> None:
        app.add_middleware(FlashMessagesMiddleware)
        app.add_template_context_processors(_context_processor)

    return extension
