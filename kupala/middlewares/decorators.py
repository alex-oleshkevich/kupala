import functools
import typing as t

from kupala.middlewares.base import BaseHTTPMiddleware


def middleware(
    *args: t.Any,
    **kwargs: t.Any,
) -> t.Callable[[t.Any], BaseHTTPMiddleware]:
    def wrapper(fn: t.Callable) -> BaseHTTPMiddleware:
        callback = functools.partial(fn, *args, **kwargs)
        return t.cast(
            BaseHTTPMiddleware, functools.partial(BaseHTTPMiddleware, dispatch=callback)
        )

    return wrapper
