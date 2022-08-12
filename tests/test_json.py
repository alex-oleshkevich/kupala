from dataclasses import dataclass

import datetime
import decimal
import enum
import io
import typing
import uuid

from kupala import json
from kupala.json import jsonify


def test_to_json() -> None:
    class Jsonable:
        def to_json(self) -> str:
            return "json"

    assert json.dumps(Jsonable()) == '"json"'


def test_jsonable() -> None:
    class Jsonable:
        def __json__(self) -> str:
            return "json"

    assert json.dumps(Jsonable()) == '"json"'


def test_uuid() -> None:
    value = uuid.uuid4()
    assert json.dumps(value) == f'"{value}"'


def test_timedelta() -> None:
    value = datetime.timedelta(seconds=5)
    assert json.dumps(value) == f'"{value}"'


def test_datetime() -> None:
    value = datetime.datetime(year=2020, month=1, day=1, hour=0, minute=0, second=0)
    assert json.dumps(value) == f'"{value.isoformat()}"'


def test_date() -> None:
    value = datetime.date(year=2020, month=1, day=1)
    assert json.dumps(value) == f'"{value.isoformat()}"'


def test_time() -> None:
    value = datetime.time(hour=1, minute=0, second=0)
    assert json.dumps(value) == f'"{value.isoformat()}"'


def test_set() -> None:
    value = {1, 2, 3}
    assert json.dumps(value) == "[1, 2, 3]"


def test_frozenset() -> None:
    value = frozenset({1, 2, 3})
    assert json.dumps(value) == "[1, 2, 3]"


def test_decimal() -> None:
    value = decimal.Decimal("3.14")
    assert json.dumps(value) == '"3.14"'


def test_dictkeys() -> None:
    value = {"key": "value"}
    assert json.dumps(value.keys()) == '["key"]'


def test_dictvalues() -> None:
    value = {"key": "value"}
    assert json.dumps(value.values()) == '["value"]'


def test_enum() -> None:
    class Example(enum.Enum):
        VALUE = "value"

    value = Example.VALUE
    assert json.dumps(value) == '"value"'


def test_bytes() -> None:
    value = b"value"
    assert json.dumps(value) == '"value"'


def test_dataclass() -> None:
    @dataclass
    class SomeDataclass:
        id: int = 1

    value = SomeDataclass()
    assert json.dumps(value) == '{"id": 1}'


def test_jsonify() -> None:
    @dataclass
    class SomeDataclass:
        id: int = 1

    date_value = datetime.date(year=2020, month=1, day=1)
    time_value = datetime.time(hour=1, minute=0, second=0)
    obj = {
        "key": "value",
        "meta": SomeDataclass(),
        "inner": {
            "dict_keys": {"key": "value"}.keys(),
            "dict_values": {"key": "value"}.values(),
        },
        "when": {"date": date_value, "time": [time_value]},
    }
    assert jsonify(obj) == {
        "key": "value",
        "meta": {
            "id": 1,
        },
        "inner": {
            "dict_keys": ["key"],
            "dict_values": ["value"],
        },
        "when": {"date": f"{date_value.isoformat()}", "time": [f"{time_value}"]},
    }


def test_dump_uses_default_callback() -> None:
    stream = io.StringIO()
    value = datetime.time(hour=1, minute=0, second=0)
    json.dump(value, stream)
    assert stream.getvalue() == f'"{value.isoformat()}"'


def test_dump_uses_custom_default_callback() -> None:
    def default(obj: typing.Any) -> typing.Any:
        return "encoded"

    stream = io.StringIO()
    value = datetime.time(hour=1, minute=0, second=0)
    json.dump(value, stream, default=default)
    assert stream.getvalue() == '"encoded"'


def test_dumps_uses_default_callback() -> None:
    value = datetime.time(hour=1, minute=0, second=0)
    assert json.dumps(value) == f'"{value.isoformat()}"'


def test_dumps_uses_custom_default_callback() -> None:
    def default(obj: typing.Any) -> typing.Any:
        return "encoded"

    value = datetime.time(hour=1, minute=0, second=0)
    assert json.dumps(value, default=default) == '"encoded"'
