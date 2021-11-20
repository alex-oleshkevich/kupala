from __future__ import annotations

import builtins as bi
import datetime as datetimelib
import decimal
import enum as enumlib
import functools
import json
import logging
import os
import pathlib
import typing as t
import uuid as uuidlib
from dotenv import load_dotenv
from urllib.parse import ParseResult, urlparse

CastFn = t.Callable[[str], t.Any]
ValidatorFn = t.Callable[[t.Any], bool]


class _Undefined:
    ...


undefined = _Undefined()


class EnvError(Exception):
    """Base class for .env related errors."""


class InvalidEnvValueError(ValueError, EnvError):
    """Raised if environment variables does not pass validation."""


def one_of_validator(value: t.Any, choices: list) -> bool:
    return value in choices


def min_max_validator(
    value: t.Union[int, float, decimal.Decimal],
    min: t.Union[int, float, decimal.Decimal] = None,
    min_inclusive: bool = True,
    max: t.Union[int, float, decimal.Decimal] = None,
    max_inclusive: bool = True,
) -> bool:
    checks: list[bool] = []
    if min:
        checks.append(value >= min if min_inclusive else value > min)
    if max:
        checks.append(value <= max if max_inclusive else value < max)
    return all(checks)


class DotEnv:
    def __init__(self, paths: t.Iterable[t.Union[str, os.PathLike[str]]], prefix: bi.str = '') -> None:
        self._prefix = prefix
        for path in paths:
            self.load(path)

    def load(self, file_path: t.Union[str, os.PathLike[str]] = None, stream: t.IO[str] = None) -> DotEnv:
        assert file_path or stream, 'Either "file_path" or "stream" must be passed to "DotEnv.load" method.'
        load_dotenv(file_path, stream)
        return self

    def get(
        self,
        name: str,
        default: t.Any = undefined,
        cast: CastFn = None,
        *,
        validators: list[ValidatorFn] = None,
        check_file: bool = False,
        prefix: bi.str = '',
    ) -> t.Any:
        key = f'{prefix or self._prefix}{name}'
        value = os.environ.get(key, default)
        if value == undefined:
            base_message = f'Environment variable "{name}" is undefined and has no default.'
            if not check_file:
                raise EnvError(base_message)

            try:
                file_path = self.get(f'{key}_FILE')
            except EnvError:
                raise EnvError(
                    f'{base_message} ' f'Also, additional "{key}_FILE" has been searched but is also undefined.'
                )

            try:
                with open(file_path, 'r') as f:
                    value = f.read()
            except FileNotFoundError:
                raise EnvError(
                    f'{base_message} ' f'Also, the file {file_path} specified by "{key}_FILE" variable does not exist.'
                )

        if value != default:
            value = cast(value) if cast else value
        if validators:
            for validator in validators:
                if not validator(value):
                    raise InvalidEnvValueError(f'Environment variable "{key}" has invalid value "{value}".')
        return value

    def int(
        self,
        name: str,
        default: t.Union[int, _Undefined] = undefined,
        *,
        validators: list[ValidatorFn] = None,
        check_file: bool = False,
        prefix: bi.str = '',
        min: int = None,
        min_inclusive: bool = True,
        max: int = None,
        max_inclusive: bool = True,
    ) -> bi.int:
        validators = validators or []
        if min or max:
            validators.append(
                functools.partial(
                    min_max_validator, min=min, min_inclusive=min_inclusive, max=max, max_inclusive=max_inclusive
                )
            )
        return self.get(name, default, int, validators=validators, check_file=check_file, prefix=prefix)

    def float(
        self,
        name: str,
        default: t.Union[float, _Undefined] = undefined,
        *,
        validators: list[ValidatorFn] = None,
        check_file: bool = False,
        prefix: bi.str = '',
        min: float = None,
        min_inclusive: bool = True,
        max: float = None,
        max_inclusive: bool = True,
    ) -> bi.float:
        validators = validators or []
        if min or max:
            validators.append(
                functools.partial(
                    min_max_validator, min=min, min_inclusive=min_inclusive, max=max, max_inclusive=max_inclusive
                )
            )
        return self.get(name, default, float, validators=validators, check_file=check_file, prefix=prefix)

    def decimal(
        self,
        name: str,
        default: t.Union[decimal.Decimal, _Undefined] = undefined,
        *,
        validators: list[ValidatorFn] = None,
        check_file: bool = False,
        prefix: bi.str = '',
        min: decimal.Decimal = None,
        min_inclusive: bool = True,
        max: decimal.Decimal = None,
        max_inclusive: bool = True,
    ) -> decimal.Decimal:
        validators = validators or []
        if min or max:
            validators.append(
                functools.partial(
                    min_max_validator, min=min, min_inclusive=min_inclusive, max=max, max_inclusive=max_inclusive
                )
            )
        return self.get(name, default, decimal.Decimal, validators=validators, check_file=check_file, prefix=prefix)

    def str(
        self,
        name: bi.str,
        default: t.Union[bi.str, _Undefined] = undefined,
        *,
        validators: list[ValidatorFn] = None,
        check_file: bool = False,
        prefix: bi.str = '',
        choices: list[bi.str] = None,
    ) -> bi.str:
        validators = validators or []
        if choices:
            validators.append(functools.partial(one_of_validator, choices=choices))
        return self.get(name, default, str, validators=validators, check_file=check_file, prefix=prefix)

    def bool(
        self,
        name: bi.str,
        default: t.Union[bool, _Undefined] = undefined,
        *,
        validators: list[ValidatorFn] = None,
        check_file: bool = False,
        prefix: bi.str = '',
        allowed_values: list[bi.str] = None,
    ) -> bi.bool:
        allowed_values = allowed_values or ['1', 'true', 't', 'yes', 'on']

        def caster(value: str) -> bi.bool:
            assert allowed_values
            return value.lower() in allowed_values

        return self.get(name, default, caster, validators=validators, check_file=check_file, prefix=prefix)

    def list(
        self,
        name: bi.str,
        default: t.Union[list, _Undefined] = undefined,
        *,
        sub_cast: CastFn = None,
        validators: list[ValidatorFn] = None,
        check_file: bi.bool = False,
        prefix: bi.str = '',
        separator: bi.str = ',',
    ) -> bi.list:
        sub_cast = sub_cast or (lambda x: x)

        def caster(value: str) -> bi.list:
            assert sub_cast
            parts = value.split(separator)
            return list(map(sub_cast, parts))

        return self.get(name, default, caster, validators=validators, check_file=check_file, prefix=prefix)

    def json(
        self,
        name: bi.str,
        default: t.Union[t.Any, _Undefined] = undefined,
        *,
        validators: bi.list[ValidatorFn] = None,
        check_file: bi.bool = False,
        prefix: bi.str = '',
    ) -> t.Any:
        return self.get(name, default, cast=json.loads, validators=validators, check_file=check_file, prefix=prefix)

    def datetime(
        self,
        name: bi.str,
        default: t.Union[datetimelib.datetime, _Undefined] = undefined,
        *,
        validators: bi.list[ValidatorFn] = None,
        check_file: bi.bool = False,
        prefix: bi.str = '',
    ) -> datetimelib.datetime:
        return self.get(
            name,
            default,
            cast=datetimelib.datetime.fromisoformat,
            validators=validators,
            check_file=check_file,
            prefix=prefix,
        )

    def date(
        self,
        name: bi.str,
        default: t.Union[datetimelib.date, _Undefined] = undefined,
        *,
        validators: bi.list[ValidatorFn] = None,
        check_file: bi.bool = False,
        prefix: bi.str = '',
    ) -> datetimelib.date:
        return self.get(
            name,
            default,
            cast=datetimelib.date.fromisoformat,
            validators=validators,
            check_file=check_file,
            prefix=prefix,
        )

    def time(
        self,
        name: bi.str,
        default: t.Union[datetimelib.time, _Undefined] = undefined,
        *,
        validators: bi.list[ValidatorFn] = None,
        check_file: bi.bool = False,
        prefix: bi.str = '',
    ) -> datetimelib.time:
        return self.get(
            name,
            default,
            cast=datetimelib.time.fromisoformat,
            validators=validators,
            check_file=check_file,
            prefix=prefix,
        )

    def timedelta(
        self,
        name: bi.str,
        default: t.Union[datetimelib.timedelta, _Undefined] = undefined,
        *,
        validators: bi.list[ValidatorFn] = None,
        check_file: bi.bool = False,
        prefix: bi.str = '',
    ) -> datetimelib.timedelta:
        def caster(value: str) -> datetimelib.timedelta:
            return datetimelib.timedelta(seconds=int(value))

        return self.get(name, default, cast=caster, validators=validators, check_file=check_file, prefix=prefix)

    def uuid(
        self,
        name: bi.str,
        default: t.Union[uuidlib.UUID, _Undefined] = undefined,
        *,
        validators: bi.list[ValidatorFn] = None,
        check_file: bi.bool = False,
        prefix: bi.str = '',
    ) -> uuidlib.UUID:
        return self.get(name, default, cast=uuidlib.UUID, validators=validators, check_file=check_file, prefix=prefix)

    def url(
        self,
        name: bi.str,
        default: t.Union[bi.str, _Undefined] = undefined,
        *,
        validators: bi.list[ValidatorFn] = None,
        check_file: bi.bool = False,
        prefix: bi.str = '',
    ) -> ParseResult:
        url = self.get(name, default, cast=urlparse, validators=validators, check_file=check_file, prefix=prefix)
        if url == default:
            url = urlparse(url)
        return url

    def log_level(
        self,
        name: bi.str,
        default: t.Union[bi.str, _Undefined] = undefined,
        *,
        validators: bi.list[ValidatorFn] = None,
        check_file: bi.bool = False,
        prefix: bi.str = '',
    ) -> bi.int:
        def caster(value: bi.str) -> bi.int:
            return logging.getLevelName(value)

        return self.get(name, default, cast=caster, validators=validators, check_file=check_file, prefix=prefix)

    def path(
        self,
        name: bi.str,
        default: t.Union[t.Union[bi.str, os.PathLike], _Undefined] = undefined,
        *,
        validators: bi.list[ValidatorFn] = None,
        check_file: bi.bool = False,
        prefix: bi.str = '',
    ) -> pathlib.Path:
        value = self.get(name, default, cast=pathlib.Path, validators=validators, check_file=check_file, prefix=prefix)
        if value == default and isinstance(value, bi.str):
            value = pathlib.Path(value)
        return value

    E = t.TypeVar('E', bound=enumlib.Enum)

    def enum(
        self,
        name: bi.str,
        enum_class: t.Type[E],
        default: t.Union[E, _Undefined] = undefined,
        *,
        validators: bi.list[ValidatorFn] = None,
        check_file: bi.bool = False,
        prefix: bi.str = '',
    ) -> E:
        def caster(value: bi.str) -> t.Any:
            for enum_value in enum_class:
                if enum_value.name == value:
                    return enum_value

        return self.get(name, default, cast=caster, validators=validators, check_file=check_file, prefix=prefix)

    __call__ = str
