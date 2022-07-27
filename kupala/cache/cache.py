from __future__ import annotations

import inspect
import os
import typing
import urllib.parse
from datetime import timedelta

from kupala.cache.backends import CacheBackend, DummyCache, FileCache, InMemoryCache
from kupala.cache.compressors import CacheCompressor, NullCompressor
from kupala.cache.serializers import CacheSerializer, JSONSerializer


def _timedelta_to_seconds(delta: timedelta | int) -> int:
    if isinstance(delta, timedelta):
        return int(delta.total_seconds())
    return delta


_BACKENDS: dict[str, typing.Type[CacheBackend]] = {
    'memory': InMemoryCache,
    'dummy': DummyCache,
    'file': FileCache,
}


def backend_from_url(url: str) -> CacheBackend:
    scheme = urllib.parse.urlparse(url).scheme
    if scheme == 'redis':
        from .backends.redis import RedisCache

        return RedisCache.from_url(url)
    try:
        return _BACKENDS[scheme].from_url(url)
    except KeyError:
        raise KeyError(f'Unknown backend: {scheme}://')


class Cache:
    backend: CacheBackend

    def __init__(
        self,
        url: str | None = None,
        *,
        backend: CacheBackend | None = None,
        prefix: str = '',
        serializer: CacheSerializer | None = None,  # todo: support literals
        compressor: CacheCompressor | None = None,  # todo: support literals
    ) -> None:
        assert url or backend, 'Either "url" or "backend" argument is required.'
        if url:
            backend = backend_from_url(url)

        assert backend
        self.backend = backend
        self.serializer = serializer or JSONSerializer()
        self.compressor = compressor or NullCompressor()
        self._prefix = prefix

    async def get(self, key: str, default: typing.Any = None) -> typing.Any:
        key = self._make_key(key)
        value = await self.backend.get(key)
        if value is None:
            return default
        return self.serializer.loads(self.compressor.decompress(value))

    async def get_many(self, keys: typing.Iterable[str]) -> dict[str, typing.Any | None]:
        keys = self._make_keys(keys)
        value = await self.backend.get_many(keys)
        return {
            k.lstrip(self._prefix): self.serializer.loads(self.compressor.decompress(v)) if v is not None else v
            for k, v in value.items()
        }

    async def get_or_set(self, key: str, default: typing.Any, seconds: int | timedelta) -> typing.Any:
        value = await self.get(key)
        if value is None:
            if callable(default):
                if inspect.iscoroutinefunction(default):
                    default = await default()
                else:
                    default = default()
            await self.set(key, default, seconds)
            value = default
        return value

    async def pull(self, key: str) -> typing.Any:
        value = await self.get(key)
        await self.delete(key)
        return value

    async def set(self, key: str, value: typing.Any, seconds: int | timedelta) -> None:
        key = self._make_key(key)
        value = self.compressor.compress(self.serializer.dumps(value))
        await self.backend.set(key, value, _timedelta_to_seconds(seconds))

    async def set_many(self, values: dict[str, typing.Any], seconds: int | timedelta) -> None:
        compressed: dict[str, bytes] = {
            self._make_key(key): self.compressor.compress(self.serializer.dumps(value)) for key, value in values.items()
        }
        await self.backend.set_many(compressed, _timedelta_to_seconds(seconds))

    async def delete(self, key: str) -> None:
        key = self._make_key(key)
        await self.backend.delete(key)

    async def delete_many(self, keys: typing.Iterable[str]) -> None:
        keys = self._make_keys(keys)
        await self.backend.delete_many(keys)

    async def clear(self) -> None:
        await self.backend.clear()

    async def touch(self, key: str, delta: int | timedelta) -> None:
        """Set a new expiration time on a key."""
        key = self._make_key(key)
        return await self.backend.touch(key, _timedelta_to_seconds(delta))

    async def increment(self, key: str, step: int = 1) -> None:
        key = self._make_key(key)
        return await self.backend.increment(key, step)

    async def decrement(self, key: str, step: int = 1) -> None:
        key = self._make_key(key)
        return await self.backend.decrement(key, step)

    async def exists(self, key: str) -> bool:
        key = self._make_key(key)
        return await self.backend.exists(key)

    def _make_key(self, key: str) -> str:
        return self._prefix + key

    def _make_keys(self, keys: typing.Iterable[str]) -> typing.Iterable[str]:
        return [self._make_key(key) for key in keys]


class CacheManager:
    def __init__(self, caches: dict[str, Cache] | None = None, default: str = 'default') -> None:
        self._default_cache_name = default
        self._caches = caches or {}

    @property
    def default(self) -> Cache:
        return self.get(self._default_cache_name)

    def get(self, name: str) -> Cache:
        assert name in self._caches, f'Cache "{name}" is not configured.'
        return self._caches[name]

    def use(self, url: str, name: str = 'default') -> CacheManager:
        self.add(name, Cache(url))
        return self

    def add(self, name: str, cache: Cache) -> CacheManager:
        assert name not in self._caches, f'Cache "{name}" already configured.'
        self._caches[name] = cache
        return self

    def add_in_memory(self, name: str, prefix: str = '') -> CacheManager:
        return self.add(name, Cache('memory://', prefix=prefix))

    def add_redis(self, name: str, redis_dsn: str, prefix: str = '') -> CacheManager:
        return self.add(name, Cache(url=redis_dsn, prefix=prefix))

    def add_dummy(self, name: str, prefix: str = '') -> CacheManager:
        return self.add(name, Cache(url='dummy://', prefix=prefix))

    def add_file(self, name: str, directory: str | os.PathLike, prefix: str = '') -> CacheManager:
        return self.add(name, Cache(backend=FileCache(directory), prefix=prefix))
