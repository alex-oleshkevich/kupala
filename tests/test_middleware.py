from starlette.middleware.base import BaseHTTPMiddleware

from kupala.middleware import Middleware, MiddlewareStack
from kupala.routing import Router


class StubMiddleware(BaseHTTPMiddleware):
    ...


class Stub2Middleware(BaseHTTPMiddleware):
    ...


def test_middleware_stack() -> None:
    stack = MiddlewareStack()
    stack.use(StubMiddleware, a=1, b=2)
    stack.use(Stub2Middleware)

    iterator = iter(stack)
    first = next(iterator)
    assert isinstance(first, Middleware)
    assert first.obj == StubMiddleware
    assert first.args == {"a": 1, "b": 2}
    assert next(iterator).obj == Stub2Middleware

    reverse = list(reversed(stack))
    assert reverse[0].obj == Stub2Middleware
    assert reverse[1].obj == StubMiddleware

    assert len(stack) == 2


def test_middleware_wraps_app() -> None:
    app = Router()
    mw = Middleware(StubMiddleware)
    wrapped = mw.wrap(app)
    assert isinstance(wrapped, StubMiddleware)


def test_middleware_is_iterable() -> None:
    mw = Middleware(StubMiddleware)
    cls, kwargs = mw
    assert cls == StubMiddleware
    assert kwargs == {}
