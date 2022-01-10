import dataclasses

import datetime
import decimal
import functools
import json
import typing
import uuid
from enum import Enum

JSONEncoder = json.JSONEncoder


def json_default(o: typing.Any) -> typing.Any:
    """Usage: json.dumps(data, default=json_default)"""
    if hasattr(o, "to_json"):
        return o.to_json()

    if hasattr(o, "__json__"):
        return o.__json__()

    if isinstance(o, (uuid.UUID, datetime.timedelta)):
        return str(o)

    if isinstance(o, datetime.datetime):
        return o.isoformat()

    if isinstance(o, datetime.date):
        return o.isoformat()

    if isinstance(o, datetime.time):
        return o.isoformat()

    if isinstance(o, (set, frozenset)):
        return list(o)

    if isinstance(o, decimal.Decimal):
        return str(o)

    if isinstance(o, Enum):
        return o.value

    if dataclasses.is_dataclass(o):
        return dataclasses.asdict(o)

    return JSONEncoder().default(o)


def walk(value: typing.Any, callback: typing.Callable) -> typing.Any:
    """Visit each item and apply"""
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
