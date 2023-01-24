from __future__ import annotations

import enum
import typing

Choices = typing.Iterable[tuple[typing.Any, typing.Any]]


class ChoicesMeta(enum.EnumMeta):
    _value_map: dict[str, typing.Any]

    def __new__(mcs, name: str, bases: tuple, attrs: typing.Any, **kwargs: typing.Any) -> ChoicesMeta:
        value_map = {}
        for key in attrs._member_names:
            member = attrs[key]
            match member:
                case list([value, label]) | tuple([value, label]):
                    value_map[value] = label
                    dict.__setitem__(attrs, key, value)
                case _:
                    value_map[member] = key.replace("_", " ").title()

        cls = super().__new__(mcs, name, bases, attrs, **kwargs)
        setattr(cls, "_value_map", value_map)
        return enum.unique(cls)  # type:ignore

    @property
    def labels(cls) -> typing.Iterable[typing.Any]:
        return tuple(cls._value_map.values())

    @property
    def values(cls) -> typing.Iterable[typing.Any]:
        return tuple(cls._value_map.keys())

    @property
    def choices(cls) -> Choices:
        return tuple([tuple([value, label]) for value, label in cls._value_map.items()])  # type: ignore[misc]


class BaseChoices(enum.Enum, metaclass=ChoicesMeta):
    pass


class IntegerChoices(int, BaseChoices):
    pass


class TextChoices(str, BaseChoices):
    def __str__(self) -> str:
        return str(self.value)
