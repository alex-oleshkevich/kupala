from __future__ import annotations

import datetime
import typing
from urllib.parse import urlparse

from kupala.cache.backends.base import CacheBackend
from kupala.cache.backends.memory import MemoryCacheBackend
from kupala.cache.backends.redis import RedisCacheBackend
from kupala.cache.serializers import CacheSerializer, JsonCacheSerializer


class Cache:
    def __init__(
        self,
        backend: CacheBackend,
        serializer: CacheSerializer | None = None,
        namespace: str = "cache",
    ) -> None:
        self.backend = backend
        self.namespace = namespace
        self.serializer = serializer or JsonCacheSerializer()

    async def set(self, key: str, value: typing.Any, ttl: datetime.timedelta | int) -> None:
        ttl_seconds = ttl.total_seconds() if isinstance(ttl, datetime.timedelta) else ttl
        await self.backend.set(self._make_key(key), self.serializer.serialize(value), int(ttl_seconds))

    async def get(self, key: str) -> typing.Any | None:
        value = await self.backend.get(self._make_key(key))
        return self.serializer.deserialize(value) if value is not None else None

    def _make_key(self, key: str) -> str:
        return f"{self.namespace}:{key}" if self.namespace else key

    @classmethod
    def from_url(
        cls,
        url: str,
        namespace: str = "cache",
        serializer: CacheSerializer | None = None,
    ) -> "Cache":
        schema = urlparse(url).scheme
        backend = MemoryCacheBackend()

        if schema in ("redis", "rediss"):
            try:
                from redis import Redis

                backend = RedisCacheBackend(Redis.from_url(url))
            except ImportError:
                raise ImportError("Redis backend requires `redis` package installed.")

        return cls(backend, serializer, namespace)
