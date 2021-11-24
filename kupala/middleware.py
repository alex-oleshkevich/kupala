from __future__ import annotations

import typing as t
from starlette.types import ASGIApp


class Middleware:
    """Keeps middleware callable along with its constructor arguments."""

    def __init__(self, obj: t.Type, **kwargs: t.Any) -> None:
        self.obj = obj
        self.args = kwargs

    def wrap(self, app: ASGIApp) -> ASGIApp:
        """Wraps ASGI application with this middleware."""
        return self.obj(app, **self.args)

    def __repr__(self) -> str:  # pragma: no cover
        return "<Middleware: %s, kwargs=%r>" % (self.obj, self.args)

    def __iter__(self) -> t.Iterator:
        return iter(tuple([self.obj, self.args]))


class MiddlewareStack:
    """Keeps track about all middleware used."""

    def __init__(self, middleware: list[Middleware] = None) -> None:
        self._global: list[Middleware] = middleware or []

    def top(self, mw: t.Type, **kwargs: t.Any) -> None:
        """Add middleware to the top of stack."""
        self._global.insert(0, Middleware(mw, **kwargs))

    def use(self, mw: t.Type, **kwargs: t.Any) -> None:
        """Add middleware to the end of stack."""
        self._global.append(Middleware(mw, **kwargs))

    def __iter__(self) -> t.Iterator[Middleware]:
        return iter(self._global)

    def __reversed__(self) -> t.Iterator[Middleware]:
        return reversed(self._global)

    def __len__(self) -> int:
        return len(self._global)

    def __str__(self) -> str:  # pragma: nocover
        return "<MiddlewareStack: %s middleware>" % (len(self),)
