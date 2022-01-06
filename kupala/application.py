from __future__ import annotations

import contextvars as cv

from kupala.app.base import BaseApp

_current_app: cv.ContextVar[Kupala] = cv.ContextVar('_current_app')


class Kupala(BaseApp):
    """Main application class."""


def set_current_application(app: Kupala) -> None:
    _current_app.set(app)


def get_current_application() -> Kupala:
    return _current_app.get()
