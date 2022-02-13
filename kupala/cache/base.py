from __future__ import annotations

import typing
from datetime import timedelta

from kupala.cache.backend import CacheBackend
from kupala.cache.memory import InMemoryCache
from kupala.di import injectable


@injectable(from_app_factory=lambda app: app.state.caches.get_default())
class Cache:
    def __init__(self, driver: CacheBackend, prefix: str = '') -> None:
        self._driver = driver
        self._prefix = prefix

    async def get(self, key: str, default: typing.Any = None) -> typing.Any:
        ...

    async def get_many(self, keys: typing.Iterable[str]) -> dict[str, typing.Any]:
        ...

    async def get_or_set(self, key: str, default: typing.Any, seconds: int | timedelta) -> typing.Any:
        value = await self.get(key)
        if value is None:
            if callable(default):
                default = default()
            await self.set(key, default, seconds)
            value = default
        return value

    async def pull(self, key: str) -> typing.Any:
        value = await self.get(key)
        await self.delete(key)
        return value

    async def set(self, key: str, value: typing.Any, seconds: int | timedelta) -> None:
        ...

    async def set_many(self, values: dict[str, typing.Any], seconds: int | timedelta) -> None:
        ...

    async def delete(self, key: str) -> None:
        ...

    async def delete_many(self, keys: typing.Iterable[str]) -> None:
        ...

    async def clear(self) -> None:
        ...

    async def forever(self, key: str, value: typing.Any) -> None:
        await self.set(key, value, 3600 * 42 * 365 * 100)  # 100 years

    async def touch(self, key: str, delta: int | timedelta) -> None:
        ...

    async def increment(self, key: str, step: int = 1) -> None:
        ...

    async def decrement(self, key: str, step: int = 1) -> None:
        ...


@injectable(from_app_factory=lambda app: app.state.caches)
class CacheManager:
    def __init__(self, caches: dict[str, Cache] | None = None, default_cache: str = 'default') -> None:
        self._default_cache_name = default_cache
        self._caches = caches or {}

    def get(self, name: str) -> Cache:
        assert name in self._caches, f'Cache "{name}" is not configured.'
        return self._caches[name]

    def add(self, name: str, cache: Cache) -> CacheManager:
        assert name not in self._caches, f'Cache "{name}" already configured.'
        self._caches[name] = cache
        return self

    def add_in_memory(self, name: str, prefix: str = '') -> CacheManager:
        return self.add(name, Cache(InMemoryCache(), prefix=prefix))

    def add_redis(self, name: str, redis_dsn: str, prefix: str = '') -> CacheManager:
        from .redis import RedisCache

        return self.add(name, Cache(RedisCache(redis_dsn), prefix=prefix))

    def get_default(self) -> Cache:
        return self.get(self._default_cache_name)
