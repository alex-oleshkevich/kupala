import abc
import typing


class CacheBackend(abc.ABC):
    @abc.abstractmethod
    async def get(self, key: str) -> bytes | None:
        ...

    @abc.abstractmethod
    async def get_many(self, keys: typing.Iterable[str]) -> dict[str, bytes]:
        ...

    @abc.abstractmethod
    async def set(self, key: str, value: bytes, ttl: int) -> None:
        ...

    @abc.abstractmethod
    async def set_many(self, value: dict[str, bytes], ttl: int) -> None:
        ...

    @abc.abstractmethod
    async def delete(self, key: str) -> None:
        ...

    @abc.abstractmethod
    async def delete_many(self, keys: typing.Iterable[str]) -> None:
        ...

    @abc.abstractmethod
    async def clear(self) -> None:
        ...

    @abc.abstractmethod
    async def increment(self, key: str, step: int) -> None:
        ...

    @abc.abstractmethod
    async def decrement(self, key: str, step: int) -> None:
        ...

    @abc.abstractmethod
    async def touch(self, key: str, delta: int) -> None:
        ...

    @abc.abstractmethod
    async def exists(self, key: str) -> bool:
        ...