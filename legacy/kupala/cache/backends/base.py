import abc


class CacheBackend(abc.ABC):  # pragma: no cover
    @abc.abstractmethod
    async def set(self, key: str, value: bytes, ttl: int) -> None:
        pass

    @abc.abstractmethod
    async def get(self, key: str) -> bytes | None:
        pass
