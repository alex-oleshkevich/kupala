import pytest

from kupala.application import Kupala, set_current_application
from kupala.cache.decorators import cached


@pytest.mark.asyncio
async def test_cached_decorator_with_async_callable() -> None:
    counter = 0

    @cached(3600)
    async def call_me() -> int:
        nonlocal counter
        counter += 1
        return counter

    app = Kupala()
    app.caches.add_in_memory('default')
    set_current_application(app)

    assert await call_me() == 1
    assert await call_me() == 1


@pytest.mark.asyncio
async def test_cached_decorator_with_async_class_method() -> None:
    class Example:
        def __init__(self) -> None:
            self.counter = 0

        @cached(3600)
        async def call_me(self) -> int:
            self.counter += 1
            return self.counter

    app = Kupala()
    app.caches.add_in_memory('default')
    set_current_application(app)

    instance = Example()
    assert await instance.call_me() == 1
    assert await instance.call_me() == 1
