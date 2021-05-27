from __future__ import annotations

import typing as t

from starlette.middleware import base
from starlette.types import ASGIApp, Receive, Scope, Send

from kupala.requests import Request
from kupala.responses import Response


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


class MiddlewareStack:
    """Keeps track about all middleware used."""

    def __init__(self) -> None:
        self._global: list[Middleware] = []
        self._groups: dict[str, MiddlewareStack] = {}

    def top(self, mw: t.Type, **kwargs: t.Any) -> None:
        """Add middleware to the top of stack."""
        self._global.insert(0, Middleware(mw, **kwargs))

    def use(self, mw: t.Type, **kwargs: t.Any) -> None:
        """Add middleware to the end of stack."""
        self._global.append(Middleware(mw, **kwargs))

    def group(self, name: str) -> MiddlewareStack:
        """Create a middleware group."""
        self._groups.setdefault(name, MiddlewareStack())
        return self._groups[name]

    def has_group(self, name: str) -> bool:
        return name in self._groups

    def __enter__(self) -> MiddlewareStack:
        return self

    def __exit__(self, *args: t.Any) -> None:
        pass

    def __iter__(self) -> t.Iterator[Middleware]:
        return iter(self._global)

    def __reversed__(self) -> t.Iterator[Middleware]:
        return reversed(self._global)

    def __len__(self) -> int:
        return len(self._global)

    def __str__(self) -> str:  # pragma: nocover
        return "<MiddlewareStack: %s middleware, %s groups>" % (
            len(self),
            len(self._groups.keys()),
        )


RequestResponseEndpoint = t.Callable[[Request], t.Awaitable[Response]]


class BaseHTTPMiddleware(base.BaseHTTPMiddleware):
    async def __call__(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
    ) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        response = await self.dispatch_func(scope["request"], self.call_next)
        await response(scope, receive, send)

    async def dispatch(  # type: ignore[override]
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        raise NotImplementedError()  # pragma: no cover
