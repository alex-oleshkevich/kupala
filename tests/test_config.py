import dataclasses
import datetime
import decimal
import enum
import ipaddress
import pathlib
import uuid

import pytest

from kupala.config import EnvReader, SettingsError


class Environment(enum.StrEnum):
    DEVELOPMENT = "development"
    PRODUCTION = "production"
    TESTING = "testing"


class TestPrimitives:
    def test_str(self) -> None:
        reader = EnvReader(source={"NAME": "hello"})
        assert reader.read(str, "NAME") == "hello"

    def test_int(self) -> None:
        reader = EnvReader(source={"PORT": "8080"})
        assert reader.read(int, "PORT") == 8080

    def test_int_invalid(self) -> None:
        reader = EnvReader(source={"PORT": "abc"})
        with pytest.raises(SettingsError, match="expected int"):
            reader.read(int, "PORT")

    def test_float(self) -> None:
        reader = EnvReader(source={"RATE": "0.5"})
        assert reader.read(float, "RATE") == 0.5

    def test_float_invalid(self) -> None:
        reader = EnvReader(source={"RATE": "abc"})
        with pytest.raises(SettingsError, match="expected float"):
            reader.read(float, "RATE")

    @pytest.mark.parametrize("value", ["true", "True", "TRUE", "1", "yes", "on"])
    def test_bool_true(self, value: str) -> None:
        reader = EnvReader(source={"DEBUG": value})
        assert reader.read(bool, "DEBUG") is True

    @pytest.mark.parametrize("value", ["false", "False", "FALSE", "0", "no", "off"])
    def test_bool_false(self, value: str) -> None:
        reader = EnvReader(source={"DEBUG": value})
        assert reader.read(bool, "DEBUG") is False

    def test_bool_invalid(self) -> None:
        reader = EnvReader(source={"DEBUG": "maybe"})
        with pytest.raises(SettingsError, match="expected bool"):
            reader.read(bool, "DEBUG")


class TestStdlibTypes:
    def test_decimal(self) -> None:
        reader = EnvReader(source={"AMOUNT": "1.50"})
        assert reader.read(decimal.Decimal, "AMOUNT") == decimal.Decimal("1.50")

    def test_decimal_invalid(self) -> None:
        reader = EnvReader(source={"AMOUNT": "not_a_number"})
        with pytest.raises(SettingsError, match="expected Decimal"):
            reader.read(decimal.Decimal, "AMOUNT")

    def test_path(self) -> None:
        reader = EnvReader(source={"DATA_DIR": "/data/uploads"})
        assert reader.read(pathlib.Path, "DATA_DIR") == pathlib.Path("/data/uploads")

    def test_uuid(self) -> None:
        reader = EnvReader(source={"APP_ID": "550e8400-e29b-41d4-a716-446655440000"})
        assert reader.read(uuid.UUID, "APP_ID") == uuid.UUID("550e8400-e29b-41d4-a716-446655440000")

    def test_uuid_invalid(self) -> None:
        reader = EnvReader(source={"APP_ID": "not-a-uuid"})
        with pytest.raises(SettingsError, match="expected UUID"):
            reader.read(uuid.UUID, "APP_ID")

    def test_date(self) -> None:
        reader = EnvReader(source={"LAUNCH": "2024-01-15"})
        assert reader.read(datetime.date, "LAUNCH") == datetime.date(2024, 1, 15)

    def test_date_invalid(self) -> None:
        reader = EnvReader(source={"LAUNCH": "not-a-date"})
        with pytest.raises(SettingsError, match="expected date"):
            reader.read(datetime.date, "LAUNCH")

    def test_datetime(self) -> None:
        reader = EnvReader(source={"STARTED": "2024-01-15T10:30:00"})
        assert reader.read(datetime.datetime, "STARTED") == datetime.datetime(2024, 1, 15, 10, 30)


class TestEnum:
    def test_by_value(self) -> None:
        reader = EnvReader(source={"ENV": "production"})
        assert reader.read(Environment, "ENV") is Environment.PRODUCTION

    def test_by_name(self) -> None:
        reader = EnvReader(source={"ENV": "PRODUCTION"})
        assert reader.read(Environment, "ENV") is Environment.PRODUCTION

    def test_invalid(self) -> None:
        reader = EnvReader(source={"ENV": "invalid"})
        with pytest.raises(SettingsError, match="expected one of"):
            reader.read(Environment, "ENV")


class TestCollections:
    def test_list_str(self) -> None:
        reader = EnvReader(source={"HOSTS": "a, b, c"})
        assert reader.read(list[str], "HOSTS") == ["a", "b", "c"]

    def test_list_int(self) -> None:
        reader = EnvReader(source={"PORTS": "80, 443, 8080"})
        assert reader.read(list[int], "PORTS") == [80, 443, 8080]

    def test_list_empty(self) -> None:
        reader = EnvReader(source={"HOSTS": ""})
        assert reader.read(list[str], "HOSTS") == []

    def test_set(self) -> None:
        reader = EnvReader(source={"TAGS": "a, b, c"})
        assert reader.read(set[str], "TAGS") == {"a", "b", "c"}

    def test_frozenset(self) -> None:
        reader = EnvReader(source={"TAGS": "a, b, c"})
        assert reader.read(frozenset[str], "TAGS") == frozenset({"a", "b", "c"})

    def test_tuple(self) -> None:
        reader = EnvReader(source={"ITEMS": "a, b, c"})
        assert reader.read(tuple[str, ...], "ITEMS") == ("a", "b", "c")

    def test_tuple_empty(self) -> None:
        reader = EnvReader(source={"ITEMS": ""})
        assert reader.read(tuple[str, ...], "ITEMS") == ()


class TestDefaults:
    def test_default_used_when_missing(self) -> None:
        reader = EnvReader(source={})
        assert reader.read(int, "PORT", default=8080) == 8080

    def test_default_factory(self) -> None:
        reader = EnvReader(source={})
        assert reader.read(list[str], "HOSTS", default_factory=lambda: ["localhost"]) == ["localhost"]

    def test_env_overrides_default(self) -> None:
        reader = EnvReader(source={"PORT": "9000"})
        assert reader.read(int, "PORT", default=8080) == 9000

    def test_required_missing_raises(self) -> None:
        reader = EnvReader(source={})
        with pytest.raises(SettingsError, match="Missing required env var.*SECRET_KEY"):
            reader.read(str, "SECRET_KEY")


class TestPrefix:
    def test_prefix_applied(self) -> None:
        reader = EnvReader(prefix="APP_", source={"APP_NAME": "test"})
        assert reader.read(str, "NAME") == "test"

    def test_prefix_in_error_message(self) -> None:
        reader = EnvReader(prefix="APP_", source={})
        with pytest.raises(SettingsError, match="APP_NAME"):
            reader.read(str, "NAME")


class TestSecretFiles:
    def test_secret_file_read(self, tmp_path: pathlib.Path) -> None:
        secret_file = tmp_path / "api_key"
        secret_file.write_text("my-secret-value\n")
        reader = EnvReader(secrets_pattern=str(tmp_path / "{name}"), source={})
        assert reader.read(str, "API_KEY", secret="api_key") == "my-secret-value"

    def test_secret_file_priority_over_env(self, tmp_path: pathlib.Path) -> None:
        secret_file = tmp_path / "api_key"
        secret_file.write_text("from-secret")
        reader = EnvReader(secrets_pattern=str(tmp_path / "{name}"), source={"API_KEY": "from-env"})
        assert reader.read(str, "API_KEY", secret="api_key") == "from-secret"

    def test_missing_secret_falls_back_to_env(self) -> None:
        reader = EnvReader(secrets_pattern="/nonexistent/{name}", source={"API_KEY": "from-env"})
        assert reader.read(str, "API_KEY", secret="api_key") == "from-env"

    def test_secret_file_with_type_casting(self, tmp_path: pathlib.Path) -> None:
        (tmp_path / "port").write_text("8080\n")
        reader = EnvReader(secrets_pattern=str(tmp_path / "{name}"), source={})
        assert reader.read(int, "PORT", secret="port") == 8080


class TestCast:
    def test_custom_cast(self) -> None:
        def parse_duration(value: str) -> datetime.timedelta:
            unit = value[-1]
            num = int(value[:-1])
            return datetime.timedelta(seconds=num * {"s": 1, "m": 60, "h": 3600}[unit])

        reader = EnvReader(source={"TTL": "5m"})
        assert reader.read(datetime.timedelta, "TTL", cast=parse_duration) == datetime.timedelta(minutes=5)

    def test_custom_cast_failure_wrapped(self) -> None:
        reader = EnvReader(source={"PORT": "abc"})
        with pytest.raises(SettingsError, match="Failed to cast"):
            reader.read(int, "PORT", cast=int)

    def test_auto_construct_ipaddress(self) -> None:
        reader = EnvReader(source={"IP": "127.0.0.1"})
        assert reader.read(ipaddress.IPv4Address, "IP") == ipaddress.IPv4Address("127.0.0.1")

    def test_auto_construct_failure(self) -> None:
        reader = EnvReader(source={"IP": "not-an-ip"})
        with pytest.raises(SettingsError, match="failed to construct"):
            reader.read(ipaddress.IPv4Address, "IP")


class TestOsEnviron:
    def test_reads_from_os_environ(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("FROM_OS", "yes")
        reader = EnvReader()
        assert reader.read(str, "FROM_OS") == "yes"


class TestDataclassIntegration:
    def test_basic(self) -> None:
        reader = EnvReader(prefix="APP_", source={"APP_NAME": "demo", "APP_PORT": "8080"})

        @dataclasses.dataclass(frozen=True)
        class Settings:
            name: str = reader.read(str, "NAME")
            port: int = reader.read(int, "PORT")
            debug: bool = reader.read(bool, "DEBUG", default=False)

        s = Settings()
        assert s.name == "demo"
        assert s.port == 8080
        assert s.debug is False

    def test_kwargs_override(self) -> None:
        reader = EnvReader(source={"NAME": "from-env"})

        @dataclasses.dataclass(frozen=True)
        class Settings:
            name: str = reader.read(str, "NAME")

        s = Settings(name="from-kwarg")
        assert s.name == "from-kwarg"

    def test_replace(self) -> None:
        reader = EnvReader(source={"NAME": "original", "DEBUG": "false"})

        @dataclasses.dataclass(frozen=True)
        class Settings:
            name: str = reader.read(str, "NAME")
            debug: bool = reader.read(bool, "DEBUG")

        s = Settings()
        s2 = dataclasses.replace(s, debug=True)
        assert s2.debug is True
        assert s2.name == "original"
        assert s.debug is False

    def test_frozen(self) -> None:
        reader = EnvReader(source={"NAME": "x"})

        @dataclasses.dataclass(frozen=True)
        class Settings:
            name: str = reader.read(str, "NAME")

        s = Settings()
        with pytest.raises(dataclasses.FrozenInstanceError):
            s.name = "y"  # type: ignore[misc]
