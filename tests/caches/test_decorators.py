import pytest

from kupala.application import set_current_application
from kupala.cache import Cache, CacheManager
from kupala.cache.decorators import cached
from tests.conftest import TestAppFactory


def make_cache_manager() -> CacheManager:
    return CacheManager(
        {
            "default": Cache("memory://"),
        }
    )


@pytest.mark.asyncio
async def test_cached_decorator_with_async_callable(test_app_factory: TestAppFactory) -> None:
    counter = 0

    @cached(3600)
    async def call_me() -> int:
        nonlocal counter
        counter += 1
        return counter

    app = test_app_factory()
    app.state.caches = make_cache_manager()
    set_current_application(app)

    assert await call_me() == 1
    assert await call_me() == 1


@pytest.mark.asyncio
async def test_cached_decorator_with_async_class_method(test_app_factory: TestAppFactory) -> None:
    class Example:
        def __init__(self) -> None:
            self.counter = 0

        @cached(3600)
        async def call_me(self) -> int:
            self.counter += 1
            return self.counter

    app = test_app_factory()
    app.state.caches = make_cache_manager()
    set_current_application(app)

    instance = Example()
    assert await instance.call_me() == 1
    assert await instance.call_me() == 1
