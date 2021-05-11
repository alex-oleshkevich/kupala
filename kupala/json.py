import dataclasses
import datetime
import decimal
import functools
import json
import typing as t
import uuid
from enum import Enum

JSONEncoder = json.JSONEncoder


def json_default(o: t.Any) -> t.Any:
    """Usage: json.dumps(data, default=json_default)"""
    if hasattr(o, "__json__"):
        return o.__json__()

    if isinstance(o, (uuid.UUID, datetime.timedelta)):
        return str(o)

    if isinstance(o, datetime.datetime):
        return o.isoformat()

    if isinstance(o, datetime.date):
        return o.isoformat()

    if isinstance(o, (set, frozenset)):
        return list(o)

    if isinstance(o, decimal.Decimal):
        return str(o)

    if isinstance(o, Enum):
        return o.value

    if isinstance(o, datetime.time):
        return o.isoformat()

    if dataclasses.is_dataclass(o):
        return dataclasses.asdict(o)

    raise TypeError(repr(o) + " is not JSON serializable")


def walk(value: t.Any, callback: t.Callable) -> t.Any:
    """Visit each item and apply"""
    if isinstance(value, dict):
        for key, value_ in value.items():
            value[key] = walk(value_, callback)

    if isinstance(value, (list, tuple, set)):
        return list(walk(x, callback) for x in value)

    if dataclasses.is_dataclass(value):
        value = dataclasses.asdict(value)
        return walk(value, callback)

    return callback(value)


def jsonify(value: t.Any) -> t.Any:
    """Visit each item and convert it into JSON serializable value."""
    return walk(value, functools.partial(json_default, throw=False))


JSONData = t.Any  # https://github.com/python/typing/issues/182


def dump(
    value: JSONData,
    fp: t.IO[str],
    default: t.Callable[[t.Any], t.Any] = json_default,
    **kwargs: t.Any,
) -> None:
    json.dump(value, fp, default=default, **kwargs)


def dumps(value: JSONData, **kwargs: t.Any) -> str:
    if "default" not in kwargs:
        kwargs["default"] = json_default
    return json.dumps(value, **kwargs)


def load(fp: t.IO[str], **kwargs: t.Any) -> str:
    return json.load(fp, **kwargs)


def loads(value: str, **kwargs: t.Any) -> JSONData:
    return json.loads(value, **kwargs)
