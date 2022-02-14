import typing

from kupala.cache import CacheBackend


class DummyCache(CacheBackend):
    async def get(self, key: str) -> bytes | None:
        return None

    async def get_many(self, keys: typing.Iterable[str]) -> dict[str, bytes]:
        return {}

    async def set(self, key: str, value: bytes, ttl: int) -> None:
        return

    async def set_many(self, value: dict[str, bytes], ttl: int) -> None:
        return

    async def delete(self, key: str) -> None:
        return

    async def delete_many(self, keys: typing.Iterable[str]) -> None:
        return

    async def clear(self) -> None:
        return

    async def increment(self, key: str, step: int) -> None:
        return

    async def decrement(self, key: str, step: int) -> None:
        return

    async def touch(self, key: str, delta: int) -> None:
        return

    async def exists(self, key: str) -> bool:
        return False
