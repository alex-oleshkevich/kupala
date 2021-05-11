import dataclasses
import datetime
import enum
import io
import uuid
from decimal import Decimal

import pytest

from kupala import json
from kupala.json import jsonify


def test_encodes_datetime():
    assert json.dumps(datetime.datetime(2021, 1, 1)) == '"2021-01-01T00:00:00"'


def test_encodes_date():
    assert json.dumps(datetime.date(2021, 1, 1)) == '"2021-01-01"'


def test_encodes_time():
    assert json.dumps(datetime.time(12, 30, 59)) == '"12:30:59"'


def test_encodes_uuid4():
    value = uuid.uuid4()
    assert json.dumps(value) == f'"{value}"'


def test_encodes_set():
    assert json.dumps({1}) == "[1]"
    assert json.dumps(frozenset([1])) == "[1]"


def test_encodes_decimal():
    assert json.dumps(Decimal(100)) == '"100"'


def test_encodes_enums():
    class Animals(enum.Enum):
        CAT = "cat"
        DOG = "dog"

    assert json.dumps(Animals.CAT) == '"cat"'


def test_encodes_dataclasses():
    @dataclasses.dataclass
    class Person:
        name: str = "root"
        index: int = 1

    assert json.dumps(Person()) == '{"name": "root", "index": 1}'


def test_encodes_jsonable_classes():
    class Person:
        name: str = "root"
        index: int = 1

        def to_json(self) -> dict:
            return {"name": self.name, "index": self.index}

    assert json.dumps(Person()) == '{"name": "root", "index": 1}'


def test_raises_for_unsupported_type():
    class Person:
        name: str = "root"
        index: int = 1

    with pytest.raises(TypeError):
        assert json.dumps(Person())


def test_jsonify():
    @dataclasses.dataclass()
    class Person:
        name: str = "root"
        index: int = 1

    actual = jsonify(
        {
            "name": "root",
            "children": [Person(), Person()],
            "mapping": {"person": Person()},
        }
    )

    assert actual == {
        "name": "root",
        "children": [{"index": 1, "name": "root"}, {"index": 1, "name": "root"}],
        "mapping": {"person": {"index": 1, "name": "root"}},
    }


def test_dump():
    buffer = io.StringIO()
    json.dump(1, buffer)
    buffer.seek(0)
    assert buffer.read() == "1"


def test_dumps():
    assert json.dumps(1) == "1"


def test_load():
    buffer = io.StringIO()
    buffer.write("1")
    buffer.seek(0)
    assert json.load(buffer) == 1


def test_loads():
    assert json.loads("1") == 1
