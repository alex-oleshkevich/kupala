from __future__ import annotations

import anyio
import contextlib
import time
import typing

from kupala.cache.backends import CacheBackend


class InMemoryCache(CacheBackend):
    def __init__(self) -> None:
        self._cache: dict[str, tuple[bytes, float]] = {}

    async def get(self, key: str) -> bytes | None:
        with contextlib.suppress(TypeError):
            value, expires = self._cache.get(key)  # type: ignore[misc]
            if expires >= time.time():
                return value

            await self.delete(key)  # delete expired key
        return None

    async def get_many(self, keys: typing.Iterable[str]) -> dict[str, bytes | None]:
        value: dict[str, bytes | None] = {}

        async def _fetch(cache_key: str) -> None:
            value[cache_key] = await self.get(cache_key)

        async with anyio.create_task_group() as tg:
            for key in keys:
                tg.start_soon(_fetch, key)
        return value

    async def set(self, key: str, value: bytes, ttl: float) -> None:
        new_ttl = time.time() + ttl
        self._cache[key] = (value, new_ttl)

    async def set_many(self, value: dict[str, bytes], ttl: int) -> None:
        async with anyio.create_task_group() as tg:
            for key, data in value.items():
                tg.start_soon(self.set, key, data, ttl)

    async def delete(self, key: str) -> None:
        self._cache.pop(key, None)

    async def delete_many(self, keys: typing.Iterable[str]) -> None:
        async with anyio.create_task_group() as tg:
            for key in keys:
                tg.start_soon(self.delete, key)

    async def clear(self) -> None:
        self._cache.clear()

    async def increment(self, key: str, step: int) -> None:
        value = int(await self.get(key) or b'0')
        await self.set(key, str(value + step).encode(), 999_999_999)

    async def decrement(self, key: str, step: int) -> None:
        value = int(await self.get(key) or b'0')
        await self.set(key, str(value - step).encode(), 999_999_999)

    async def touch(self, key: str, delta: int) -> None:
        pair = self._cache.get(key)
        if pair:
            await self.set(key, pair[0], delta)

    async def exists(self, key: str) -> bool:
        pair = self._cache.get(key)
        if not pair:
            return False
        expired = self._is_expired(pair[1])
        if expired:
            await self.delete(key)
            return False
        return True

    def _is_expired(self, value: float) -> bool:
        return time.time() > value

    @classmethod
    def from_url(cls: typing.Type[InMemoryCache], url: str) -> InMemoryCache:
        return cls()
