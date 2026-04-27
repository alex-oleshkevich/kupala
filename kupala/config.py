from __future__ import annotations

import datetime
import decimal
import enum
import os
import pathlib
import typing
import uuid
from collections.abc import Callable, Mapping
from typing import Any, overload

from kupala.exceptions import KupalaError

_UNSET: Any = object()


class SettingsError(KupalaError):
    pass


class EnvReader:
    def __init__(
        self,
        *,
        prefix: str = "",
        secrets_pattern: str = "/run/secrets/{name}",
        source: Mapping[str, str] | None = None,
    ) -> None:
        self.prefix = prefix
        self.secrets_pattern = secrets_pattern
        self.source: Mapping[str, str] = source if source is not None else os.environ

    @overload
    def read[T](
        self,
        typ: type[T],
        name: str,
        *,
        secret: str | None = None,
        cast: Callable[[str], T] | None = None,
    ) -> T: ...
    @overload
    def read[T](
        self,
        typ: type[T],
        name: str,
        *,
        default: T,
        secret: str | None = None,
        cast: Callable[[str], T] | None = None,
    ) -> T: ...
    @overload
    def read[T](
        self,
        typ: type[T],
        name: str,
        *,
        default_factory: Callable[[], T],
        secret: str | None = None,
        cast: Callable[[str], T] | None = None,
    ) -> T: ...

    def read(
        self,
        typ: Any,
        name: str,
        *,
        default: Any = _UNSET,
        default_factory: Callable[[], Any] | None = None,
        secret: str | None = None,
        cast: Callable[[str], Any] | None = None,
    ) -> Any:
        env_name = self.prefix + name
        raw: str | None = None
        if secret:
            try:
                with open(self.secrets_pattern.format(name=secret)) as f:
                    raw = f.read().strip()
            except OSError:
                pass
        if raw is None:
            raw = self.source.get(env_name)
        if raw is None:
            if default is not _UNSET:
                return default
            if default_factory is not None:
                return default_factory()
            raise SettingsError(f"Missing required env var {env_name!r}")
        if cast is not None:
            try:
                return cast(raw)
            except Exception as e:
                raise SettingsError(f"Failed to cast {env_name}={raw!r}: {e}") from e
        return _builtin_cast(raw, typ, env_name)


def _builtin_cast(raw: str, typ: Any, env_name: str) -> Any:
    origin = typing.get_origin(typ)
    if origin in (list, set, frozenset, tuple):
        args = typing.get_args(typ)
        elem_type = args[0]
        items = [_builtin_cast(p.strip(), elem_type, env_name) for p in raw.split(",")] if raw.strip() else []
        if origin is list:
            return items
        if origin is set:
            return set(items)
        if origin is frozenset:
            return frozenset(items)
        return tuple(items)

    if typ is str:
        return raw
    if typ is int:
        try:
            return int(raw)
        except ValueError as e:
            raise SettingsError(f"{env_name}: expected int, got {raw!r}") from e
    if typ is float:
        try:
            return float(raw)
        except ValueError as e:
            raise SettingsError(f"{env_name}: expected float, got {raw!r}") from e
    if typ is bool:
        lower = raw.strip().lower()
        if lower in frozenset({"true", "1", "yes", "on"}):
            return True
        if lower in frozenset({"false", "0", "no", "off"}):
            return False
        raise SettingsError(f"{env_name}: expected bool, got {raw!r}")
    if typ is decimal.Decimal:
        try:
            return decimal.Decimal(raw)
        except decimal.InvalidOperation as e:
            raise SettingsError(f"{env_name}: expected Decimal, got {raw!r}") from e
    if typ is pathlib.Path:
        return pathlib.Path(raw)
    if typ is uuid.UUID:
        try:
            return uuid.UUID(raw)
        except ValueError as e:
            raise SettingsError(f"{env_name}: expected UUID, got {raw!r}") from e
    if typ is datetime.datetime:
        try:
            return datetime.datetime.fromisoformat(raw)
        except ValueError as e:
            raise SettingsError(f"{env_name}: expected datetime, got {raw!r}") from e
    if typ is datetime.date:
        try:
            return datetime.date.fromisoformat(raw)
        except ValueError as e:
            raise SettingsError(f"{env_name}: expected date, got {raw!r}") from e
    if isinstance(typ, type) and issubclass(typ, enum.Enum):
        try:
            return typ(raw)
        except ValueError:
            try:
                return typ[raw]
            except KeyError as e:
                values = [m.value for m in typ]
                raise SettingsError(f"{env_name}: expected one of {values}, got {raw!r}") from e

    try:
        return typ(raw)
    except Exception as e:
        type_name = typ.__name__ if isinstance(typ, type) else repr(typ)
        raise SettingsError(f"{env_name}: failed to construct {type_name}({raw!r}): {e}") from e
