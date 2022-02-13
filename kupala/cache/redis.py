import typing

from kupala.cache.backend import CacheBackend


class RedisCache(CacheBackend):
    def __init__(self, dsn: str) -> None:
        self.dsn = dsn

    async def get(self, key: str) -> typing.Any:
        pass

    async def get_many(self, keys: typing.Iterable[str]) -> dict[str, typing.Any]:
        pass

    async def set(self, key: str, ttl: int) -> None:
        pass

    async def set_many(self, value: dict[str, typing.Any], ttl: int) -> None:
        pass

    async def delete(self, key: str) -> None:
        pass

    async def delete_many(self, keys: typing.Iterable[str]) -> None:
        pass

    async def clear(self) -> None:
        pass

    async def increment(self, key: str, step: int) -> None:
        pass

    async def decrement(self, key: str, step: int) -> None:
        pass

    async def touch(self, key: str, delta: int) -> None:
        pass
