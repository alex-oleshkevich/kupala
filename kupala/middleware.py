import functools
import typing

from kupala.requests import Request
from kupala.responses import Response
from kupala.types import ASGIApp, ASGIMiddleware

type CallNext = typing.Callable[[Request[typing.Any]], typing.Awaitable[Response]]
type Middleware = typing.Callable[[Request[typing.Any]], CallNext]

P = typing.ParamSpec("P")


def with_options(
    middleware: typing.Callable[typing.Concatenate[ASGIApp, P], ASGIApp],
    *args: P.args,
    **kwargs: P.kwargs,
) -> ASGIMiddleware:
    @functools.wraps(middleware)
    def factory(app: ASGIApp) -> ASGIApp:
        return middleware(app, *args, **kwargs)

    return factory


def build_asgi_middleware_stack(middlewares: typing.Sequence[ASGIMiddleware], router: ASGIApp) -> ASGIApp:
    app: ASGIApp = router
    for middleware in reversed(middlewares):
        app = middleware(app)
    return app
