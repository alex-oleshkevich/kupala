from __future__ import annotations

import builtins as bi
import decimal
import functools
import os
import typing as t
from dotenv import load_dotenv

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
    def __init__(self, paths: t.Iterable[t.Union[str, os.PathLike[str]]], prefix: str = '') -> None:
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
    ) -> t.Any:
        key = f'{self._prefix}{name}'
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
        return self.get(name, default, int, validators=validators, check_file=check_file)

    def float(
        self,
        name: str,
        default: t.Union[float, _Undefined] = undefined,
        *,
        validators: list[ValidatorFn] = None,
        check_file: bool = False,
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
        return self.get(name, default, float, validators=validators, check_file=check_file)

    def decimal(
        self,
        name: str,
        default: t.Union[decimal.Decimal, _Undefined] = undefined,
        *,
        validators: list[ValidatorFn] = None,
        check_file: bool = False,
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
        return self.get(name, default, decimal.Decimal, validators=validators, check_file=check_file)

    def str(
        self,
        name: bi.str,
        default: t.Union[bi.str, _Undefined] = undefined,
        *,
        validators: list[ValidatorFn] = None,
        check_file: bool = False,
        choices: list[bi.str] = None,
    ) -> bi.str:
        validators = validators or []
        if choices:
            validators.append(functools.partial(one_of_validator, choices=choices))
        return self.get(name, default, str, validators=validators, check_file=check_file)

    def bool(
        self,
        name: bi.str,
        default: t.Union[bool, _Undefined] = undefined,
        *,
        validators: list[ValidatorFn] = None,
        check_file: bool = False,
        allowed_values: list[bi.str] = None,
    ) -> bi.bool:
        allowed_values = allowed_values or ['1', 'true', 't', 'yes', 'on']

        def caster(value: str) -> bi.bool:
            assert allowed_values
            return value.lower() in allowed_values

        return self.get(name, default, caster, validators=validators, check_file=check_file)

    def list(
        self,
        name: bi.str,
        default: t.Union[list, _Undefined] = undefined,
        *,
        sub_cast: CastFn = None,
        validators: list[ValidatorFn] = None,
        check_file: bi.bool = False,
        separator: bi.str = ',',
    ) -> bi.list:
        sub_cast = sub_cast or (lambda x: x)

        def caster(value: str) -> bi.list:
            assert sub_cast
            parts = value.split(separator)
            return list(map(sub_cast, parts))

        return self.get(name, default, caster, validators=validators, check_file=check_file)
