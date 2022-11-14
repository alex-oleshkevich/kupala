import inspect
import typing
from starlette.types import ASGIApp, Receive, Scope, Send


def _covert_into_class(fn: typing.Callable) -> typing.Type[ASGIApp]:
    class _InnerApp:
        def __init__(self, app: typing.Callable) -> None:
            self.app = app

        async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
            func = fn(self.app)
            await func(scope, receive, send)

    return _InnerApp


class Middleware:
    """Keeps middleware callable along with its constructor arguments."""

    def __init__(self, obj: typing.Any, **kwargs: typing.Any) -> None:
        if inspect.isfunction(obj):
            obj = _covert_into_class(obj)

        self.obj = obj
        self.args = kwargs

    def wrap(self, app: ASGIApp) -> ASGIApp:
        """Wraps ASGI application with this middleware."""
        return self.obj(app, **self.args)

    def __repr__(self) -> str:  # pragma: no cover
        return "<Middleware: %s, kwargs=%r>" % (self.obj, self.args)

    def __iter__(self) -> typing.Iterator:
        yield self.obj
        yield self.args


class MiddlewareStack:
    """Keeps track about all middleware used."""

    def __init__(self, middleware: list[Middleware] | None = None) -> None:
        self._global: list[Middleware] = middleware or []

    def add(self, mw: Middleware) -> None:
        self._global.append(mw)

    def top(self, mw: typing.Type, **kwargs: typing.Any) -> None:
        """Add middleware to the top of stack."""
        self._global.insert(0, Middleware(mw, **kwargs))

    def use(self, mw: typing.Type, **kwargs: typing.Any) -> None:
        """Add middleware to the end of stack."""
        self._global.append(Middleware(mw, **kwargs))

    def __iter__(self) -> typing.Iterator[Middleware]:
        return iter(self._global)

    def __reversed__(self) -> typing.Iterator[Middleware]:
        return reversed(self._global)

    def __len__(self) -> int:
        return len(self._global)

    def __str__(self) -> str:  # pragma: nocover
        return "<MiddlewareStack: %s middleware>" % (len(self),)
