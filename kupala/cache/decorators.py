import functools
import typing
from datetime import timedelta

from kupala.application import get_current_application
from kupala.cache import CacheManager

_PS = typing.ParamSpec('_PS')
_RT = typing.TypeVar('_RT', bound=typing.Awaitable)


class cached:
    """
    Cache function calls.

    This decorator requires running application.
    """

    def __init__(self, ttl: int | timedelta, key: str | None = None, name: str = 'default') -> None:
        self.ttl = ttl
        self.name = name
        self.key = key

    def __call__(self, fn: typing.Callable[_PS, _RT]) -> typing.Callable[_PS, typing.Awaitable[_RT]]:
        if self.key is None:
            self.key = '.'.join([fn.__module__, fn.__name__])

        @functools.wraps(fn)
        async def wrapper(*args: _PS.args, **kwargs: _PS.kwargs) -> _RT:
            app = get_current_application()
            cache = app.dependencies.get(CacheManager).get(self.name)

            async def _call_fn() -> _RT:
                return await fn(*args, **kwargs)

            assert self.key
            return await cache.get_or_set(self.key, _call_fn, self.ttl)

        return wrapper
