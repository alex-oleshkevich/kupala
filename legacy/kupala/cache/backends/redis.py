import typing

from kupala.cache.backends.base import CacheBackend

try:
    from redis.asyncio import Redis
except ImportError:
    Redis = None


class RedisCacheBackend(CacheBackend):
    def __init__(self, redis_client: Redis) -> None:
        assert Redis is not None, "Redis backend requires `redis` package installed."
        self.redis_client = redis_client

    async def set(self, key: str, value: bytes, ttl: int) -> None:
        async with self.redis_client as conn:
            await conn.set(key, value, ex=ttl)

    async def get(self, key: str) -> bytes | None:
        async with self.redis_client as conn:
            return typing.cast(bytes | None, await conn.get(key))
