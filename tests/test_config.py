import datetime
import decimal
import json
import os
import pathlib
from pathlib import Path

import pytest

from kupala.config import Env


class TestEnvInit:
    def test_env_files_single_string(self, tmp_path: Path) -> None:
        env_file = tmp_path / ".env"
        env_file.write_text("FOO=bar\n")
        env = Env(environ={}, env_files=str(env_file))
        assert env.get("FOO") == "bar"

    def test_init_does_not_mutate_os_environ(self) -> None:
        before = dict(os.environ)
        Env(environ={"KUPALA_TEST_NEW_KEY_XYZ": "y"})
        after = dict(os.environ)
        assert before == after


class TestEnvLoadDotenv:
    def test_load_dotenv(self, tmp_path: Path) -> None:
        env_file = tmp_path / ".env"
        env_file.write_text("FOO=bar\nBAZ=qux\n")
        env = Env(environ={})
        env.load_dotenv(env_file)
        assert env.get("FOO") == "bar"
        assert env.get("BAZ") == "qux"

    def test_load_dotenv_missing_file(self, tmp_path: Path) -> None:
        env = Env(environ={})
        with pytest.raises(FileNotFoundError):
            env.load_dotenv(tmp_path / "nonexistent.env")

    def test_load_dotenv_if_exists(self, tmp_path: Path) -> None:
        env = Env(environ={"SEED": "x"})
        env.load_dotenv_if_exists(tmp_path / "missing.env")

        env_file = tmp_path / ".env"
        env_file.write_text("KUPALA_TEST_LOAD_KEY_XYZ=value\n")
        env.load_dotenv_if_exists(env_file)
        assert env.get("KUPALA_TEST_LOAD_KEY_XYZ") == "value"

    def test_does_not_override_environ(self, tmp_path: Path) -> None:
        env_file = tmp_path / ".env"
        env_file.write_text("PORT=fromfile\n")
        env = Env(environ={"PORT": "fromenv"})
        env.load_dotenv(env_file)
        assert env.get("PORT") == "fromenv"


class TestEnvGet:
    def test_get(self) -> None:
        env = Env(environ={"FOO": "bar"})
        assert env.get("FOO") == "bar"

    def test_get_with_cast(self) -> None:
        env = Env(environ={"PORT": "8080"})
        assert env.get("PORT", cast=int) == 8080

    def test_get_with_default(self) -> None:
        env = Env(environ={})
        assert env.get("MISSING", default="d") == "d"

    def test_get_with_cast_and_default(self) -> None:
        env = Env(environ={})
        assert env.get("MISSING", cast=int, default=80) == 80

    def test_get_missing_raises(self) -> None:
        env = Env(environ={"SEED": "x"})
        with pytest.raises(ValueError):
            env.get("MISSING_KEY_XYZ")

    def test_get_with_prefix(self) -> None:
        env = Env(environ={"APP_FOO": "bar"}, env_prefix="APP_")
        assert env.get("FOO") == "bar"


class TestEnvInt:
    def test_parse(self) -> None:
        env = Env(environ={"PORT": "8080"})
        assert env.int("PORT") == 8080

    def test_default(self) -> None:
        env = Env(environ={})
        assert env.int("PORT", default=80) == 80

    def test_invalid_raises(self) -> None:
        env = Env(environ={"PORT": "abc"})
        with pytest.raises(ValueError):
            env.int("PORT")


class TestEnvFloat:
    def test_parse(self) -> None:
        env = Env(environ={"RATIO": "0.5"})
        assert env.float("RATIO") == 0.5

    def test_default(self) -> None:
        env = Env(environ={"SEED": "x"})
        assert env.float("MISSING", default=1.0) == 1.0

    def test_invalid_raises(self) -> None:
        env = Env(environ={"RATIO": "abc"})
        with pytest.raises(ValueError):
            env.float("RATIO")


class TestEnvBool:
    @pytest.mark.parametrize("value", ["1", "true", "yes", "on", "TRUE", "True", "Yes", "ON"])
    def test_truthy(self, value: str) -> None:
        env = Env(environ={"FLAG": value})
        assert env.bool("FLAG") is True

    @pytest.mark.parametrize("value", ["0", "false", "no", "off", "FALSE", "False", "No", "OFF"])
    def test_falsy(self, value: str) -> None:
        env = Env(environ={"FLAG": value})
        assert env.bool("FLAG") is False

    @pytest.mark.parametrize("value", [" true ", "\ntrue\t", " on "])
    def test_strips_whitespace(self, value: str) -> None:
        env = Env(environ={"FLAG": value})
        assert env.bool("FLAG") is True

    @pytest.mark.parametrize("value", ["", "2", "maybe", "y", "n", "tru"])
    def test_invalid_raises(self, value: str) -> None:
        env = Env(environ={"FLAG": value})
        with pytest.raises(ValueError):
            env.bool("FLAG")


class TestEnvStr:
    def test_parse(self) -> None:
        env = Env(environ={"NAME": "kupala"})
        assert env.str("NAME") == "kupala"

    def test_default(self) -> None:
        env = Env(environ={"SEED": "x"})
        assert env.str("MISSING", default="d") == "d"


class TestEnvDecimal:
    def test_parse(self) -> None:
        env = Env(environ={"PRICE": "1.99"})
        assert env.decimal("PRICE") == decimal.Decimal("1.99")

    def test_default(self) -> None:
        env = Env(environ={"SEED": "x"})
        d = decimal.Decimal("0")
        assert env.decimal("MISSING", default=d) == d

    def test_invalid_raises(self) -> None:
        env = Env(environ={"PRICE": "abc"})
        with pytest.raises(decimal.InvalidOperation):
            env.decimal("PRICE")


class TestEnvDate:
    def test_parse(self) -> None:
        env = Env(environ={"WHEN": "2026-01-15"})
        assert env.date("WHEN") == datetime.date(2026, 1, 15)

    def test_default(self) -> None:
        env = Env(environ={"SEED": "x"})
        d = datetime.date(2000, 1, 1)
        assert env.date("MISSING", default=d) == d


class TestEnvDateTime:
    def test_parse(self) -> None:
        env = Env(environ={"WHEN": "2026-01-15T10:30:00"})
        assert env.datetime("WHEN") == datetime.datetime(2026, 1, 15, 10, 30, 0)


class TestEnvTime:
    def test_parse(self) -> None:
        env = Env(environ={"WHEN": "10:30:00"})
        assert env.time("WHEN") == datetime.time(10, 30, 0)


class TestEnvTimedelta:
    def test_seconds_only(self) -> None:
        env = Env(environ={"TTL": "5"})
        assert env.timedelta("TTL") == datetime.timedelta(seconds=5)

    def test_hours_minutes(self) -> None:
        env = Env(environ={"TTL": "1:30"})
        assert env.timedelta("TTL") == datetime.timedelta(hours=1, minutes=30)

    def test_hours_minutes_seconds(self) -> None:
        env = Env(environ={"TTL": "1:30:45"})
        assert env.timedelta("TTL") == datetime.timedelta(hours=1, minutes=30, seconds=45)

    def test_float_components(self) -> None:
        env = Env(environ={"TTL": "1.5:30"})
        assert env.timedelta("TTL") == datetime.timedelta(hours=1.5, minutes=30)

    @pytest.mark.parametrize("value", ["abc", "1:2:3:4", "1:", ":30"])
    def test_invalid_raises(self, value: str) -> None:
        env = Env(environ={"TTL": value})
        with pytest.raises(ValueError):
            env.timedelta("TTL")


class TestEnvPath:
    def test_parse(self) -> None:
        env = Env(environ={"HOME": "/home/user"})
        result = env.path("HOME")
        assert result == pathlib.Path("/home/user")
        assert isinstance(result, pathlib.Path)

    def test_default(self) -> None:
        env = Env(environ={"SEED": "x"})
        default = pathlib.Path("/")
        assert env.path("MISSING", default=default) == default


class TestEnvList:
    def test_parse(self) -> None:
        env = Env(environ={"ITEMS": "a,b,c"})
        assert env.list("ITEMS") == ["a", "b", "c"]

    def test_with_item_cast(self) -> None:
        env = Env(environ={"PORTS": "8080,8081,8082"})
        assert env.list("PORTS", item_cast=int) == [8080, 8081, 8082]

    def test_strips_whitespace(self) -> None:
        env = Env(environ={"ITEMS": "a, b , c"})
        assert env.list("ITEMS") == ["a", "b", "c"]

    def test_default(self) -> None:
        env = Env(environ={"SEED": "x"})
        assert env.list("MISSING", default=["x"]) == ["x"]


class TestEnvJsonList:
    def test_parse(self) -> None:
        env = Env(environ={"DATA": "[1, 2, 3]"})
        assert env.json_list("DATA") == [1, 2, 3]

    def test_default(self) -> None:
        env = Env(environ={"SEED": "x"})
        assert env.json_list("MISSING", default=[1, 2]) == [1, 2]

    def test_invalid_raises(self) -> None:
        env = Env(environ={"DATA": "not json"})
        with pytest.raises(json.JSONDecodeError):
            env.json_list("DATA")


class TestEnvJsonDict:
    def test_parse(self) -> None:
        env = Env(environ={"DATA": '{"a": 1, "b": 2}'})
        assert env.json_dict("DATA") == {"a": 1, "b": 2}

    def test_default(self) -> None:
        env = Env(environ={"SEED": "x"})
        assert env.json_dict("MISSING", default={"k": 1}) == {"k": 1}

    def test_invalid_raises(self) -> None:
        env = Env(environ={"DATA": "not json"})
        with pytest.raises(json.JSONDecodeError):
            env.json_dict("DATA")
