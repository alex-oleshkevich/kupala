import dataclasses

import collections.abc
import datetime
import decimal
import enum
import functools
import typing
import uuid
from babel.support import LazyProxy

try:
    import ujson as json  # type: ignore[import]
except ImportError:
    import json  # type: ignore[no-redef]

JSONEncoder = json.JSONEncoder

_type_to_encoder: dict[type, typing.Callable] = {
    uuid.UUID: str,
    datetime.timedelta: str,
    datetime.datetime: lambda x: x.isoformat(),
    datetime.date: lambda x: x.isoformat(),
    datetime.time: lambda x: x.isoformat(),
    set: list,
    frozenset: list,
    collections.abc.KeysView: list,
    collections.abc.ValuesView: list,
    decimal.Decimal: str,
    bytes: lambda x: x.decode(),
    LazyProxy: str,
    enum.Enum: lambda x: x.value,
}


def json_default(o: typing.Any) -> typing.Any:
    """Usage: json.dumps(data, default=json_default)"""
    if hasattr(o, "to_json"):
        return o.to_json()

    if hasattr(o, "__json__"):
        return o.__json__()

    for type_class, encoder in _type_to_encoder.items():
        if isinstance(o, type_class):
            return encoder(o)

    if dataclasses.is_dataclass(o):
        return dataclasses.asdict(o)

    return JSONEncoder().default(o)


def walk(value: typing.Any, callback: typing.Callable) -> typing.Any:
    """Visit each item and apply."""
    if isinstance(value, dict):
        for key, value_ in value.items():
            value[key] = walk(value_, callback)

    if isinstance(value, (list, tuple, set)):
        return list(walk(x, callback) for x in value)

    if dataclasses.is_dataclass(value):
        value = dataclasses.asdict(value)
        return walk(value, callback)

    try:
        return callback(value)
    except TypeError:
        return value


def jsonify(value: typing.Any) -> typing.Any:
    """Visit each item and convert it into JSON serializable value."""
    return walk(value, functools.partial(json_default))


JSONData = typing.Any  # https://github.com/python/typing/issues/182


def dump(
    value: JSONData,
    fp: typing.IO[str],
    default: typing.Callable[[typing.Any], typing.Any] = json_default,
    **kwargs: typing.Any,
) -> None:
    json.dump(value, fp, default=default, **kwargs)


def dumps(value: JSONData, **kwargs: typing.Any) -> str:
    if "default" not in kwargs and "cls" not in kwargs:
        kwargs["default"] = json_default
    return json.dumps(value, **kwargs)


load = json.load
loads = json.loads
