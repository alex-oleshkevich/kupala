import builtins
import contextlib
import datetime as _dt
import json
import os
import pathlib
import typing
from decimal import Decimal

import dotenv

from kupala.types import MISSING, Undefined

T = typing.TypeVar("T")


type EnvFilePaths[T] = list[T] | tuple[T, ...]


class Env:
    def __init__(
        self,
        *,
        environ: dict[str, str] | None = None,
        env_files: str | os.PathLike[str] | EnvFilePaths[str | os.PathLike[str]] | None = None,
        env_prefix: str = "",
    ) -> None:
        self.env_prefix = env_prefix
        self.environ = environ or os.environ.copy()
        if env_files is not None:
            env_files = env_files if isinstance(env_files, list | tuple) else [env_files]
            for env_file in env_files:
                self.load_dotenv_if_exists(env_file)

    def load_dotenv(self, file_path: str | os.PathLike[str], interpolate: bool = True) -> None:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Dotenv file {file_path} does not exists.")

        read_values = dotenv.dotenv_values(file_path, interpolate=interpolate)
        new_values = {k: v for k, v in read_values.items() if k not in self.environ and v is not None}
        self.environ.update(new_values)

    def load_dotenv_if_exists(self, file_path: str | os.PathLike[str], interpolate: bool = True) -> None:
        with contextlib.suppress(FileNotFoundError):
            self.load_dotenv(file_path, interpolate=interpolate)

    def get(
        self,
        key: str,
        cast: typing.Callable[[str], T] | None = None,
        default: T | Undefined = MISSING,
    ) -> T:
        full_key = self.env_prefix + key
        raw = self.environ.get(full_key)

        if raw is None:
            if isinstance(default, Undefined):
                raise ValueError(f'Config key "{key}" is not set and has no default value.')
            return default

        if cast is not None:
            return cast(raw)
        return typing.cast(T, raw)

    def int(self, key: builtins.str, default: builtins.int | Undefined = MISSING) -> builtins.int:
        return self.get(key, cast=builtins.int, default=default)

    def float(self, key: builtins.str, default: builtins.float | Undefined = MISSING) -> builtins.float:
        return self.get(key, cast=builtins.float, default=default)

    def bool(self, key: builtins.str, default: builtins.bool | Undefined = MISSING) -> builtins.bool:
        return self.get(key, cast=_parse_bool, default=default)

    def str(self, key: builtins.str, default: builtins.str | Undefined = MISSING) -> builtins.str:
        return self.get(key, default=default)

    def decimal(self, key: builtins.str, default: Decimal | Undefined = MISSING) -> Decimal:
        return self.get(key, cast=Decimal, default=default)

    def date(self, key: builtins.str, default: _dt.date | Undefined = MISSING) -> _dt.date:
        return self.get(key, cast=_dt.date.fromisoformat, default=default)

    def datetime(self, key: builtins.str, default: _dt.datetime | Undefined = MISSING) -> _dt.datetime:
        return self.get(key, cast=_dt.datetime.fromisoformat, default=default)

    def time(self, key: builtins.str, default: _dt.time | Undefined = MISSING) -> _dt.time:
        return self.get(key, cast=_dt.time.fromisoformat, default=default)

    def timedelta(self, key: builtins.str, default: _dt.timedelta | Undefined = MISSING) -> _dt.timedelta:
        return self.get(key, cast=_parse_timedelta, default=default)

    def path(self, key: builtins.str, default: pathlib.Path | Undefined = MISSING) -> pathlib.Path:
        return self.get(key, cast=pathlib.Path, default=default)

    def list(
        self,
        key: builtins.str,
        item_cast: typing.Callable[[builtins.str], T] = builtins.str,  # type: ignore[assignment]
        default: builtins.list[T] | Undefined = MISSING,
    ) -> builtins.list[T]:
        return self.get(
            key,
            cast=lambda v: [item_cast(item.strip()) for item in v.split(",")],
            default=default,
        )

    def json_list(
        self, key: builtins.str, default: builtins.list[typing.Any] | Undefined = MISSING
    ) -> builtins.list[typing.Any]:
        return self.get(key, cast=json.loads, default=default)

    def json_dict(
        self,
        key: builtins.str,
        default: builtins.dict[builtins.str, typing.Any] | Undefined = MISSING,
    ) -> builtins.dict[builtins.str, typing.Any]:
        return self.get(key, cast=json.loads, default=default)


def _parse_bool(value: str) -> bool:
    if value.lower().strip() in ["1", "true", "yes", "on"]:
        return True
    if value.lower().strip() in ["0", "false", "no", "off"]:
        return False
    raise ValueError(f'"{value}" is not a valid boolean value.')


def _parse_timedelta(value: str) -> _dt.timedelta:
    parts = value.split(":")
    match parts:
        case [hours, minutes, seconds]:
            return _dt.timedelta(hours=float(hours), minutes=float(minutes), seconds=float(seconds))

        case [hours, minutes]:
            return _dt.timedelta(hours=float(hours), minutes=float(minutes))
        case [seconds] if seconds:
            return _dt.timedelta(seconds=float(seconds))

    raise ValueError(f'"{value}" is not a valid timedelta value.')
