import time

from kupala.cache.backends.base import CacheBackend


class MemoryCacheBackend(CacheBackend):
    def __init__(self) -> None:
        self.cache: dict[str, tuple[bytes, float]] = {}

    async def set(self, key: str, value: bytes, ttl: int) -> None:
        self.cache[key] = (value, time.time() + ttl)

    async def get(self, key: str) -> bytes | None:
        item = self.cache.get(key)
        if not item:
            return None
        value, expire = item
        if expire < time.time():
            del self.cache[key]
            return None
        return value
