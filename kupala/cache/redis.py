import typing

from kupala.cache import CacheBackend


class RedisCache(CacheBackend):
    def __init__(self, url: str, **redis_kwargs: typing.Any) -> None:
        import aioredis

        self.redis = aioredis.from_url(url, **redis_kwargs)

    async def get(self, key: str) -> bytes | None:
        return await self.redis.get(key)

    async def get_many(self, keys: typing.Iterable[str]) -> dict[str, bytes]:
        values = dict(zip(keys, await self.redis.mget(keys)))
        return {k: v for k, v in values.items() if v is not None}

    async def set(self, key: str, value: bytes, ttl: int) -> None:
        if ttl < 0:
            await self.delete(key)
        else:
            await self.redis.set(key, value, ttl)

    async def set_many(self, value: dict[str, bytes], ttl: int) -> None:
        await self.redis.mset(value)

    async def delete(self, key: str) -> None:
        await self.redis.delete(key)

    async def delete_many(self, keys: typing.Iterable[str]) -> None:
        await self.redis.delete(*keys)

    async def clear(self) -> None:
        await self.redis.flushdb()

    async def increment(self, key: str, step: int) -> None:
        await self.redis.incr(key, step)

    async def decrement(self, key: str, step: int) -> None:
        await self.redis.decr(key, step)

    async def touch(self, key: str, delta: int) -> None:
        await self.redis.expire(key, delta)

    async def exists(self, key: str) -> bool:
        return await self.redis.exists(key) == 1
