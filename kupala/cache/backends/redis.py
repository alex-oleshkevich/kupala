from __future__ import annotations

import aioredis
import typing
import urllib.parse

from kupala.cache.backends import CacheBackend


class RedisCache(CacheBackend):
    redis: aioredis.Redis

    def __init__(
        self,
        url: str | None = None,
        *,
        redis: aioredis.Redis | None = None,
        key_prefix: str = '',
        **redis_kwargs: typing.Any,
    ) -> None:
        assert url or redis, 'Either "url" or "redis" argument must be passed.'
        if url:
            redis = aioredis.from_url(url, **redis_kwargs)

        assert redis
        self.key_prefix = key_prefix
        self.redis = redis

    async def get(self, key: str) -> bytes | None:
        key = self.make_key(key)
        return await self.redis.get(key)

    async def get_many(self, keys: typing.Iterable[str]) -> dict[str, bytes | None]:
        original_keys = keys
        keys = [self.make_key(key) for key in keys]
        return dict(zip(original_keys, await self.redis.mget(keys)))

    async def set(self, key: str, value: bytes, ttl: int) -> None:
        key = self.make_key(key)
        if ttl < 0:
            await self.delete(key)
        else:
            await self.redis.set(key, value, ttl)

    async def set_many(self, value: dict[str, bytes], ttl: int) -> None:
        value = {self.make_key(k): v for k, v in value.items()}
        await self.redis.mset(value)

    async def delete(self, key: str) -> None:
        key = self.make_key(key)
        await self.redis.delete(key)

    async def delete_many(self, keys: typing.Iterable[str]) -> None:
        keys = [self.make_key(key) for key in keys]
        await self.redis.delete(*keys)

    async def clear(self) -> None:
        await self.redis.flushdb()

    async def increment(self, key: str, step: int) -> None:
        key = self.make_key(key)
        await self.redis.incr(key, step)

    async def decrement(self, key: str, step: int) -> None:
        key = self.make_key(key)
        await self.redis.decr(key, step)

    async def touch(self, key: str, delta: int) -> None:
        key = self.make_key(key)
        await self.redis.expire(key, delta)

    async def exists(self, key: str) -> bool:
        key = self.make_key(key)
        return await self.redis.exists(key) == 1

    def make_key(self, key: str) -> str:
        return self.key_prefix + key

    @classmethod
    def from_url(cls: typing.Type[RedisCache], url: str) -> RedisCache:
        components = urllib.parse.urlparse(url)
        key_prefix = urllib.parse.parse_qs(components.query).get('key_prefix', [''])[0]
        return RedisCache(url, key_prefix=key_prefix)
