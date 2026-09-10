"""Bindings that read values out of the HTTP request."""

import dataclasses
import datetime
import decimal
import enum
import typing
import uuid

from starlette.datastructures import FormData, QueryParams
from starlette.requests import HTTPConnection

from kupala import inspection, openapi
from kupala.binders import ModelBinder
from kupala.dependencies import (
    CompileContext,
    InvalidDependencyError,
    InvocationContext,
    ParamInfo,
    Resolver,
    enter_dependency,
)
from kupala.errors import ValidationError
from kupala.requests import Request

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


@dataclasses.dataclass(frozen=True)
class RequestBinding:
    """Read a model out of one part of the request.

    This is the extension point for a new source. A subclass says where its values live and how they
    arrive, and the alias beside it is what an endpoint actually writes:

        class HeaderValue(KeyedBinding):
            label = "Header"
            coerce = True

            async def load(self, ctx: InvocationContext) -> Headers:
                connection = await ctx.resolve(HTTPConnection)
                return connection.headers


        type Header[T] = typing.Annotated[T, HeaderValue()]

    Subclass `KeyedBinding` when the source carries named values, and this class directly when it
    carries a single document, as `JSONBody` does.
    """

    # whether values arrive as strings and have to be converted before anything can type-check them
    coerce: typing.ClassVar[bool]

    async def load(self, ctx: InvocationContext) -> typing.Any:
        """Read this binding's part of the request."""

        raise NotImplementedError

    def compile(self, context: CompileContext, param: ParamInfo) -> Resolver:
        # one ordered decision taken once: a binder claims the whole source, or a converter takes one key
        binder = next((candidate for candidate in context.binders if candidate.supports(param.type)), None)
        if binder is None:
            return self.compile_scalar(param)

        return self.compile_model(binder, param)

    def compile_model(self, binder: ModelBinder, param: ParamInfo) -> Resolver:
        # the binder answers every question about the model here, once, and never on the request path
        build = binder.compile(param.type, coerce=self.coerce)

        async def resolve(ctx: InvocationContext) -> object:
            return build(await self.load(ctx))

        return resolve

    def compile_scalar(self, param: ParamInfo) -> Resolver:
        """Bind a single value rather than a whole model, for the sources that carry named values."""

        raise NotImplementedError


@dataclasses.dataclass(frozen=True)
class KeyedBinding(RequestBinding):
    """Read one named value, or a whole model, out of a mapping of request values.

    `label` names the source in error messages, so a rejected value reads as "Query parameter 'page'"
    rather than something generic.

    A scalar annotation binds one key. The parameter name is that key, and `name` overrides it when
    the client sends something a Python parameter cannot spell:

        async def search(
            q: Query[str],                                             # ?q=coffee
            source: typing.Annotated[str, QueryParam("utm-source")],   # ?utm-source=newsletter
            page: Query[int] = 1,                                      # absent -> 1
        ) -> Response: ...

    A model annotation binds the whole mapping in one go, and a repeated key fills any field that
    holds a sequence:

        class Filters(pydantic.BaseModel):
            page: int = 1
            tags: list[str] = []


        async def search(filters: Query[Filters]) -> Response: ...     # ?page=2&tags=a&tags=b

    `Form[T]` reads the submitted form the same way, so the same endpoint shape works for both.
    """

    name: str | None = None

    # names this source in the messages a rejected value produces
    label: typing.ClassVar[str]

    def compile_scalar(self, param: ParamInfo) -> Resolver:
        name = self.name or param.name
        type_label = inspection.type_name(param.type)
        # a source whose values arrive already typed has no string to hand a converter
        convert = converter_for(param.type) if self.coerce else None
        if convert is None:
            raise InvalidDependencyError(
                f"{self.label} {name!r} is annotated {type_label}, which no model binder claims and "
                f"which cannot be read as a single value. Annotate it with {self.accepted_types()}."
            )

        async def resolve(ctx: InvocationContext) -> object:
            data = await self.load(ctx)
            if name not in data:
                if not param.optional:
                    # the map is keyed by the name the client sent, which `QueryParam(...)` may rename
                    raise ValidationError(
                        f"{self.label} {name!r} is required.",
                        errors={name: "This field is required."},
                    )

                # the default is whatever the signature says, so it is never converted
                return param.default

            value = data[name]
            if not isinstance(value, str):
                # a form carries uploads alongside its text fields, and a converter only handles strings
                raise self.not_convertible(name, type_label)

            try:
                return convert(value)
            except CONVERSION_ERRORS as exc:
                raise self.not_convertible(name, type_label) from exc

        return resolve

    def accepted_types(self) -> str:
        """Name what a single value of this source may be annotated with."""

        return f"a model, or one of: {SUPPORTED_TYPES}" if self.coerce else "a model"

    def not_convertible(self, name: str, type_label: str) -> ValidationError:
        # name the expectation, never the submitted value, which would reach the logs
        return ValidationError(
            f"{self.label} {name!r} must be {type_label}.",
            errors={name: f"This field must be {type_label}."},
        )


class QueryParam(KeyedBinding):
    """Read one value, or a whole model, from the query string."""

    label = "Query parameter"
    coerce = True

    async def load(self, ctx: InvocationContext) -> QueryParams:
        # the base connection rather than the request, so query binding also works in a WebSocket handler
        connection = await ctx.resolve(HTTPConnection)
        return connection.query_params

    def to_openapi(self, param_info: ParamInfo, context: openapi.SchemaContext) -> openapi.Contribution:
        name = self.name or param_info.name
        if context.is_model(param_info.type):
            properties, required = context.properties_of(param_info.type)
            if param_info.optional:
                required = frozenset()
            return openapi.Contribution(
                parameters=tuple(
                    openapi.Parameter(
                        name=field,
                        in_=openapi.ParameterLocation.QUERY,
                        required=field in required,
                        schema=schema,
                    )
                    for field, schema in properties.items()
                )
            )
        return openapi.Contribution(
            parameters=(
                openapi.Parameter(
                    name=name,
                    in_=openapi.ParameterLocation.QUERY,
                    required=not param_info.optional,
                    schema=context.schema_for(param_info.type),
                ),
            ),
        )


class FormParam(KeyedBinding):
    """Read one value, or a whole model, from the submitted form."""

    label = "Form field"
    coerce = True

    async def load(self, ctx: InvocationContext) -> FormData:
        request = await ctx.resolve(Request)
        # a form holds spooled upload files, so its lifetime has to end with the invocation
        return typing.cast(FormData, await enter_dependency(ctx, request.form()))

    def to_openapi(self, param_info: ParamInfo, context: openapi.SchemaContext) -> openapi.Contribution:
        name = self.name or param_info.name
        if context.is_model(param_info.type):
            schema = context.schema_for(param_info.type)
        else:
            field = context.schema_for(param_info.type)
            schema = {
                "type": "object",
                "properties": {name: field},
                "required": [name] if not param_info.optional else [],
            }
        return openapi.Contribution(
            request_body=openapi.RequestBody(
                content={"application/x-www-form-urlencoded": openapi.MediaType(schema=schema)},
                required=not param_info.optional,
            )
        )


class JSONBody(RequestBinding):
    """Read a model from the JSON request body."""

    coerce = False

    async def load(self, ctx: InvocationContext) -> typing.Any:
        request = await ctx.resolve(Request)
        try:
            return await request.json()
        except ValueError as exc:
            # a body that will not parse is the client's mistake, not an unhandled server error
            raise ValidationError(
                "Body must be a JSON document.",
                errors={"": "Expected a JSON document."},
            ) from exc

    def compile_scalar(self, param: ParamInfo) -> Resolver:
        raise InvalidDependencyError(
            f"Body is annotated {inspection.type_name(param.type)}, which no model binder claims. "
            f"A request body is a document, so annotate it with a model and read single values "
            f"from the query string, the path, a header, or a cookie."
        )

    def to_openapi(self, param_info: ParamInfo, context: openapi.SchemaContext) -> openapi.Contribution:
        return openapi.Contribution(
            request_body=openapi.RequestBody(
                content={"application/json": openapi.MediaType(schema=context.schema_for(param_info.type))},
                required=not param_info.optional,
            )
        )


type Query[T] = typing.Annotated[T, QueryParam()]
type Form[T] = typing.Annotated[T, FormParam()]
type Body[T] = typing.Annotated[T, JSONBody()]
