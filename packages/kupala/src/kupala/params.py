"""Bindings that read values out of the HTTP request."""

import dataclasses
import datetime
import decimal
import enum
import typing
import uuid

from starlette.requests import HTTPConnection

from kupala import inspection
from kupala.dependencies import (
    CompileContext,
    InvalidDependencyError,
    InvocationContext,
    ParamInfo,
    Resolver,
)
from kupala.errors import ValidationError

type Converter = typing.Callable[[str], typing.Any]

TRUTHY = frozenset({"1", "true", "yes", "on"})


def to_bool(value: str) -> bool:
    """A query string carries no booleans, and bool("false") is True."""

    return value.strip().casefold() in TRUTHY


# every type a request value can be turned into, and the callable that does it
CONVERTERS: dict[typing.Any, Converter] = {
    str: str,
    int: int,
    float: float,
    bool: to_bool,
    decimal.Decimal: decimal.Decimal,
    uuid.UUID: uuid.UUID,
    datetime.date: datetime.date.fromisoformat,
    datetime.time: datetime.time.fromisoformat,
    datetime.datetime: datetime.datetime.fromisoformat,
}

# Decimal reports a bad value as InvalidOperation, which is an ArithmeticError rather than a ValueError
CONVERSION_ERRORS = (TypeError, ValueError, ArithmeticError)

SUPPORTED_TYPES = ", ".join(sorted(inspection.type_name(type_) for type_ in CONVERTERS)) + ", or an Enum"


def converter_for(type_: typing.Any) -> Converter | None:
    """Find how to turn a request string into `type_`, or None when nothing can."""

    # a lookup asks whether the key is present, never whether the converter is truthy
    converter = CONVERTERS.get(type_)
    if converter is not None:
        return converter

    if isinstance(type_, type) and issubclass(type_, enum.Enum):
        return type_

    return None


@dataclasses.dataclass(frozen=True, slots=True)
class QueryParam:
    """Read one value from the query string."""

    name: str | None = None

    def compile(self, context: CompileContext, param: ParamInfo) -> Resolver:
        name = self.name or param.name
        type_label = inspection.type_name(param.type)
        convert = converter_for(param.type)
        if convert is None:
            raise InvalidDependencyError(
                f"Query parameter {name!r} is annotated {type_label}, "
                f"which cannot be read from a query string. Annotate it with one of: {SUPPORTED_TYPES}."
            )

        async def resolve(ctx: InvocationContext) -> object:
            connection = await ctx.resolve(HTTPConnection)
            if name not in connection.query_params:
                if not param.optional:
                    # the map is keyed by the name the client sent, which `QueryParam(...)` may rename
                    raise ValidationError(
                        f"Query parameter {name!r} is required.",
                        errors={name: ["This field is required."]},
                    )

                # the default is whatever the signature says, so it is never converted
                return param.default

            try:
                return convert(connection.query_params[name])
            except CONVERSION_ERRORS as exc:
                # name the expectation, never the submitted value, which would reach the logs
                raise ValidationError(
                    f"Query parameter {name!r} must be {type_label}.",
                    errors={name: [f"This field must be {type_label}."]},
                ) from exc

        return resolve


type Query[T] = typing.Annotated[T, QueryParam()]
