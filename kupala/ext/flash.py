import typing

from kupala.application import App
from kupala.http import Request
from kupala.http.middleware import FlashMessagesMiddleware
from kupala.http.middleware.flash_messages import flash


def _context_processor(request: Request) -> dict[str, typing.Any]:
    return {
        "flash_messages": flash(request),
    }


def use_flash_messages(app: App) -> None:
    """Enable session support."""

    app.add_middleware(FlashMessagesMiddleware)
    app.add_template_context_processors(_context_processor)
