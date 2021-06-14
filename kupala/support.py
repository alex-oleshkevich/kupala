import typing as t

T = t.TypeVar("T")


class Bag(t.Generic[T]):
    def __init__(self, items: list[T]) -> None:
        self.items = items

    def first(self) -> t.Optional[T]:
        return self.items[0] if self.items else None

    def __bool__(self) -> bool:
        return len(self.items) > 0

    def __iter__(self) -> t.Iterator[T]:
        return iter(self.items)

    def __str__(self) -> str:
        return str(self.first())


class DictBag(t.Generic[T]):
    def __init__(self, data: dict[str, list[T]]):
        self.data = data

    def get(self, key: str) -> Bag[T]:
        return Bag(self.data.get(key, []))

    def keys(self) -> t.Iterable[str]:
        return self.data.keys()

    def __bool__(self) -> bool:
        return len(list(self.keys())) > 0

    def __getattr__(self, item: str) -> Bag[T]:
        return self.get(item)

    def __repr__(self) -> str:
        return "<DictBag: %r>" % self.data
