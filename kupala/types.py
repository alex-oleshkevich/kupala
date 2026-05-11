import dataclasses
import typing

from asgiref.typing import ASGI3Application, ASGIReceiveCallable, ASGISendCallable
from asgiref.typing import WWWScope as ASGIScope

type ASGIApp = ASGI3Application
type Receive = ASGIReceiveCallable
type Send = ASGISendCallable
type Scope = ASGIScope
type ASGIMiddleware = typing.Callable[[ASGIApp], ASGIApp]

__all__ = ["ASGIApp", "Receive", "Scope", "Send", "ASGIMiddleware", "MultiDict", "MutableMultiDict"]


class Undefined: ...


MISSING = Undefined()


class MultiDict[K = str, V = str](typing.Mapping[K, V]):
    """Read-only multi-value mapping."""

    def __init__(self, items: typing.Iterable[tuple[K, V]] = ()) -> None:
        self._list: list[tuple[K, V]] = list(items)

    @classmethod
    def from_bytes(cls, raw: typing.Iterable[tuple[bytes, bytes]]) -> typing.Self:
        """Build from ASGI-raw bytes pairs (latin-1 per HTTP spec)."""
        return cls((k.decode("latin-1"), v.decode("latin-1")) for k, v in raw)  # type: ignore[misc]

    def __getitem__(self, key: K) -> V:
        for k, v in reversed(self._list):
            if k == key:
                return v
        raise KeyError(key)

    def __contains__(self, key: object) -> bool:
        return any(k == key for k, _ in self._list)

    def __iter__(self) -> typing.Iterator[K]:
        seen: set[K] = set()
        for k, _ in self._list:
            if k not in seen:
                seen.add(k)
                yield k

    def __len__(self) -> int:
        seen: set[K] = set()
        for k, _ in self._list:
            seen.add(k)
        return len(seen)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, MultiDict):
            return NotImplemented
        return sorted(self._list) == sorted(other._list)

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self._list!r})"

    def getlist(self, key: K) -> list[V]:
        return [v for k, v in self._list if k == key]

    def multi_items(self) -> list[tuple[K, V]]:
        return list(self._list)


class MutableMultiDict[K = str, V = str](MultiDict[K, V]):
    """Mutable multi-value mapping."""

    def __setitem__(self, key: K, value: V) -> None:
        self.setlist(key, [value])

    def __delitem__(self, key: K) -> None:
        if key not in self:
            raise KeyError(key)
        self._list = [(k, v) for k, v in self._list if k != key]

    def pop(self, key: K, default: V | None = None) -> V | None:
        values = [v for k, v in self._list if k == key]
        if not values:
            return default
        self._list = [(k, v) for k, v in self._list if k != key]
        return values[-1]

    def popitem(self) -> tuple[K, V]:
        if not self._list:
            raise KeyError("popitem(): MultiDict is empty")
        seen: set[K] = set()
        unique_keys: list[K] = []
        for k, _ in self._list:
            if k not in seen:
                seen.add(k)
                unique_keys.append(k)
        last_key = unique_keys[-1]
        value = self[last_key]
        self._list = [(k, v) for k, v in self._list if k != last_key]
        return last_key, value

    def poplist(self, key: K) -> list[V]:
        values = [v for k, v in self._list if k == key]
        self._list = [(k, v) for k, v in self._list if k != key]
        return values

    def clear(self) -> None:
        self._list.clear()

    def setdefault(self, key: K, default: V) -> V:
        if key not in self:
            self._list.append((key, default))
            return default
        return self[key]

    def setlist(self, key: K, values: list[V]) -> None:
        if not values:
            self._list = [(k, v) for k, v in self._list if k != key]
            return
        self._list = [(k, v) for k, v in self._list if k != key] + [(key, v) for v in values]

    def append(self, key: K, value: V) -> None:
        self._list.append((key, value))

    def update(
        self,
        other: "MultiDict[K, V] | typing.Mapping[K, V] | typing.Iterable[tuple[K, V]]",
    ) -> None:
        if isinstance(other, MultiDict):
            pairs = other.multi_items()
        elif isinstance(other, typing.Mapping):
            pairs = list(other.items())
        else:
            pairs = list(other)
        replaced_keys = {k for k, _ in pairs}
        self._list = [(k, v) for k, v in self._list if k not in replaced_keys] + pairs


@dataclasses.dataclass
class ProblemDetail:
    status: int
    type: str | None = None
    instance: str | None = None
    title: str | None = None
