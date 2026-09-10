import collections.abc
import types
import typing

from kupala import inspection
from kupala.errors import ValidationError

# a string is itself a Sequence, and treating one as multi-valued would explode it into characters
SCALAR_SEQUENCES = (str, bytes, bytearray)

SEQUENCES = (collections.abc.Sequence, collections.abc.Set)


# turns one request's values into one validated object, with every model question already answered
type ModelFactory = typing.Callable[[typing.Any], typing.Any]


class ModelBinder(typing.Protocol):
    """Turn the values a request carries into a validated object, and describe that object."""

    def supports(self, type_: typing.Any) -> bool:
        """Whether this binder can validate `type_`."""
        ...

    def compile(self, type_: typing.Any, *, coerce: bool) -> ModelFactory:
        """Prepare to validate `type_`, answering every question about its shape exactly once.

        `coerce` says the values arrive as strings, which no mapping can reveal about itself. It is
        fixed for the life of the route, so introspecting the model belongs here, never on the
        request path.
        """
        ...

    def schema(self, type_: typing.Any) -> typing.Mapping[str, typing.Any]:
        """JSON Schema for `type_`, as the library emits it, including any nested `$defs`."""
        ...


def flatten(data: typing.Any, sequences: frozenset[str]) -> typing.Any:
    """Collapse a multidict, keeping repeated values only under the keys a sequence field reads."""

    # whether a key can repeat is a property of the mapping, so the data answers it rather than a flag:
    # cookies, path params and a JSON document are plain mappings with nothing to collapse
    if not hasattr(data, "getlist"):
        return data

    # unknown keys are carried over too, so a model that forbids extras can actually reject them
    return {key: data.getlist(key) if key in sequences else data[key] for key in data}


def holds_a_sequence(annotation: typing.Any) -> bool:
    """Whether a repeated request key is a sensible way to fill this annotation."""

    # a model may declare its field as `type Tags = list[str]`, and both libraries report the alias verbatim
    annotation = inspection.unwrap_alias(annotation)
    origin = typing.get_origin(annotation)
    if origin is types.UnionType:
        return any(holds_a_sequence(argument) for argument in typing.get_args(annotation))

    type_ = origin or annotation
    return isinstance(type_, type) and issubclass(type_, SEQUENCES) and not issubclass(type_, SCALAR_SEQUENCES)


class PydanticBinder:
    """Validate pydantic models. Only a claimed model reaches `compile`, so only it imports pydantic."""

    def supports(self, type_: typing.Any) -> bool:
        # duck-typing keeps pydantic out of the import graph of every application that does not use it
        return isinstance(type_, type) and hasattr(type_, "model_validate") and hasattr(type_, "model_fields")

    def compile(self, type_: typing.Any, *, coerce: bool) -> ModelFactory:
        import pydantic

        # a field is read from the wire under its alias when it has one
        sequences = frozenset(
            field.alias or name for name, field in type_.model_fields.items() if holds_a_sequence(field.annotation)
        )

        def build(data: typing.Any) -> typing.Any:
            data = flatten(data, sequences)

            try:
                # `coerce` is not passed on: pydantic coerces by default, and forcing it would override
                # a model that deliberately declared `strict=True`
                return type_.model_validate(data)
            except pydantic.ValidationError as exc:
                errors: dict[str, list[str]] = {}
                # every `include_` is off because url, context and input can each echo the value back
                for error in exc.errors(include_url=False, include_context=False, include_input=False):
                    field = ".".join(str(part) for part in error["loc"])
                    errors.setdefault(field, []).append(error["msg"])

                raise ValidationError(errors=errors) from exc

        return build

    def schema(self, type_: typing.Any) -> typing.Mapping[str, typing.Any]:
        schema: typing.Mapping[str, typing.Any] = type_.model_json_schema()
        return schema


class MsgspecBinder:
    """Validate msgspec structs. msgspec reports no field location, so its errors land under one key."""

    def supports(self, type_: typing.Any) -> bool:
        return isinstance(type_, type) and hasattr(type_, "__struct_fields__")

    def compile(self, type_: typing.Any, *, coerce: bool) -> ModelFactory:
        import msgspec

        # `get_type_hints` is the expensive part, which is exactly why it happens once and not per request
        hints = typing.get_type_hints(type_)
        # a renamed struct is read from the wire under its encoded name, parallel to the field name
        sequences = frozenset(
            encoded
            for encoded, name in zip(type_.__struct_encode_fields__, type_.__struct_fields__, strict=True)
            if holds_a_sequence(hints[name])
        )

        def build(data: typing.Any) -> typing.Any:
            data = flatten(data, sequences)

            try:
                # query and form values are always strings, so those models need the lax path to see an int
                return msgspec.convert(data, type_, strict=not coerce)
            except msgspec.ValidationError as exc:
                # msgspec names the type and the location but not the field, so there is nothing to key on
                raise ValidationError(errors={"": str(exc)}) from exc

        return build

    def schema(self, type_: typing.Any) -> typing.Mapping[str, typing.Any]:
        import msgspec

        return msgspec.json.schema(type_)


DEFAULT_MODEL_BINDERS: tuple[ModelBinder, ...] = (PydanticBinder(), MsgspecBinder())
