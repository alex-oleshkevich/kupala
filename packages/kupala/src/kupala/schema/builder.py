import collections.abc
import dataclasses
import datetime
import decimal
import enum
import typing
import uuid

from starlette.convertors import Convertor
from starlette.routing import compile_path

from kupala import inspection
from kupala.binders import DEFAULT_MODEL_BINDERS, ModelBinder
from kupala.dependencies import ParamInfo, find_binding
from kupala.routing import RouteDefinition, Routes
from kupala.schema import openapi

__all__ = [
    "DuplicateOperationError",
    "OpenAPIBuilder",
    "SchemaNamer",
    "build_document",
    "default_schema_namer",
    "path_parameters",
]

# Starlette's convertors, as the schema each one guarantees the endpoint will receive. Keyed by class
# because a convertor carries no name, and the class is not the spelling: `{id:int}` is IntegerConvertor
CONVERTOR_SCHEMAS: typing.Final[typing.Mapping[str, openapi.Schema]] = {
    "StringConvertor": {"type": "string"},
    "PathConvertor": {"type": "string", "format": "path"},
    "IntegerConvertor": {"type": "integer"},
    "FloatConvertor": {"type": "number"},
    "UUIDConvertor": {"type": "string", "format": "uuid"},
}

SCALAR_SCHEMAS: typing.Final[typing.Mapping[type, openapi.Schema]] = {
    str: {"type": "string"},
    int: {"type": "integer"},
    float: {"type": "number"},
    bool: {"type": "boolean"},
    decimal.Decimal: {"type": "string", "format": "decimal"},
    uuid.UUID: {"type": "string", "format": "uuid"},
    datetime.date: {"type": "string", "format": "date"},
    datetime.time: {"type": "string", "format": "time"},
    datetime.datetime: {"type": "string", "format": "date-time"},
}

DEFAULT_RESPONSES: typing.Final[openapi.Responses] = {
    "200": openapi.Response(description="Successful response."),
}

FORM_MEDIA_TYPE: typing.Final = "application/x-www-form-urlencoded"
JSON_MEDIA_TYPE: typing.Final = "application/json"

# names already assigned in a document; the namer must not return one that is taken
type SchemaNamer = typing.Callable[[type, collections.abc.Set[str]], str]


def default_schema_namer(type_: type, taken: collections.abc.Set[str]) -> str:
    """Prefer the class name, then qualify with the module until the name is free."""

    module = type_.__module__
    candidates = (
        type_.__name__,
        f"{module.rsplit('.', 1)[-1]}.{type_.__name__}",
        f"{module}.{type_.__qualname__}",
    )
    for candidate in candidates:
        if candidate not in taken:
            return candidate

    raise ValueError(
        f"Cannot give {inspection.type_name(type_)} a unique schema name; {candidates[-1]!r} is already used."
    )


class DuplicateOperationError(ValueError):
    """Raised when two documented routes would share one operation id."""


def convertor_schema(convertor: Convertor[typing.Any]) -> openapi.Schema:
    # a custom convertor says nothing about its output, so the widest accurate schema is a string
    return CONVERTOR_SCHEMAS.get(type(convertor).__name__, {"type": "string"})


def path_parameters(path: str) -> tuple[str, tuple[openapi.Parameter, ...]]:
    """Split a route path into its OpenAPI template and the parameters that template declares.

    Starlette spells a converted variable `{id:int}`, which OpenAPI writes as `{id}` with the type in
    the parameter's schema. The specification also requires every variable to be declared, so these
    are emitted whether or not the endpoint reads them.
    """

    _, template, convertors = compile_path(path)
    parameters = tuple(
        openapi.Parameter(
            name=name,
            in_=openapi.ParameterLocation.PATH,
            required=True,
            schema=convertor_schema(convertor),
        )
        for name, convertor in convertors.items()
    )
    return template, parameters


def merge_parameters(
    generated: tuple[openapi.Parameter, ...],
    authored: typing.Sequence[openapi.Parameter | openapi.Reference] | None,
) -> tuple[openapi.Parameter | openapi.Reference, ...] | None:
    """The parameters a path declares, plus whatever its author declared beside them."""

    if not authored:
        return generated or None

    claimed = {(p.name, p.in_) for p in authored if isinstance(p, openapi.Parameter)}
    return (*(p for p in generated if (p.name, p.in_) not in claimed), *authored)


def documented_methods(definition: RouteDefinition) -> tuple[str, ...]:
    """The methods of a definition worth documenting, lowercased for a path item."""

    methods = tuple(dict.fromkeys(method.lower() for method in definition.methods))
    # `get()` registers HEAD alongside GET, and a HEAD entry beside its GET only repeats it
    if "get" in methods:
        methods = tuple(method for method in methods if method != "head")
    return methods


def _rewrite_refs(value: typing.Any, mapping: typing.Mapping[str, str]) -> typing.Any:
    if isinstance(value, dict):
        ref = value.get("$ref")
        if isinstance(ref, str):
            name = ref.rsplit("/", 1)[-1]
            if name in mapping:
                return {**value, "$ref": f"#/components/schemas/{mapping[name]}"}
        return {key: _rewrite_refs(item, mapping) for key, item in value.items()}
    if isinstance(value, list):
        return [_rewrite_refs(item, mapping) for item in value]
    return value


def _split_library_schema(schema: openapi.Schema) -> tuple[openapi.Schema, dict[str, openapi.Schema]]:
    defs = dict(schema.get("$defs") or schema.get("definitions") or {})
    root = {key: value for key, value in schema.items() if key not in {"$defs", "definitions"}}
    ref = root.get("$ref")
    if isinstance(ref, str) and set(root) <= {"$ref"}:
        name = ref.rsplit("/", 1)[-1]
        if name in defs:
            return defs.pop(name), defs
    return root, defs


class OpenAPIBuilder:
    """The context `to_openapi` uses: binders, unique names, scalar fallbacks."""

    def __init__(
        self,
        binders: tuple[ModelBinder, ...] = DEFAULT_MODEL_BINDERS,
        namer: SchemaNamer = default_schema_namer,
    ) -> None:
        self.binders = binders
        self.namer = namer
        self.schemas: dict[str, openapi.Schema] = {}
        self.types: dict[type, str] = {}

    def name_for(self, type_: type) -> str:
        if type_ in self.types:
            return self.types[type_]

        taken = set(self.schemas) | set(self.types.values())
        name = self.namer(type_, taken)
        owner = next((existing for existing, assigned in self.types.items() if assigned == name), None)
        if name in taken and owner is not type_:
            raise ValueError(f"Schema name {name!r} for {inspection.type_name(type_)} is already used.")
        self.types[type_] = name
        return name

    def register(self, type_: type, schema: openapi.Schema) -> openapi.Schema:
        if type_ in self.types:
            return {"$ref": f"#/components/schemas/{self.types[type_]}"}

        root, defs = _split_library_schema(schema)
        name = self.name_for(type_)
        mapping = {name: name}
        for def_name in defs:
            mapping[def_name] = def_name if def_name not in self.schemas or def_name == name else f"{name}.{def_name}"

        self.schemas[name] = typing.cast(openapi.Schema, _rewrite_refs(root, mapping))
        for def_name, def_schema in defs.items():
            stored = mapping[def_name]
            if stored in self.schemas and stored != name:
                continue
            self.schemas[stored] = typing.cast(openapi.Schema, _rewrite_refs(def_schema, mapping))
        return {"$ref": f"#/components/schemas/{name}"}

    def binder_for(self, type_: typing.Any) -> ModelBinder | None:
        return next((binder for binder in self.binders if binder.supports(type_)), None)

    def is_model(self, type_: typing.Any) -> bool:
        return self.binder_for(type_) is not None

    def schema_for(self, type_: typing.Any) -> openapi.Schema:
        binder = self.binder_for(type_)
        if binder is not None:
            if not isinstance(type_, type):
                raise ValueError(f"Cannot describe {inspection.type_name(type_)} as a JSON Schema.")
            return self.register(type_, binder.schema(type_))

        scalar = SCALAR_SCHEMAS.get(type_)
        if scalar is not None:
            return scalar
        if isinstance(type_, type) and issubclass(type_, enum.Enum):
            values = [member.value for member in type_]
            json_type = "string" if all(isinstance(value, str) for value in values) else "integer"
            return {"type": json_type, "enum": values}

        raise ValueError(f"Cannot describe {inspection.type_name(type_)} as a JSON Schema.")

    def properties_of(self, type_: typing.Any) -> tuple[typing.Mapping[str, openapi.Schema], frozenset[str]]:
        schema = self.schema_for(type_)
        if "$ref" in schema and isinstance(type_, type):
            stored = self.schemas[self.types[type_]]
        else:
            stored = schema
        properties = typing.cast(typing.Mapping[str, openapi.Schema], stored.get("properties") or {})
        required = frozenset(typing.cast(typing.Sequence[str], stored.get("required") or ()))
        return properties, required

    def resolve(self, schema: openapi.Schema) -> openapi.Schema:
        ref = schema.get("$ref")
        if isinstance(ref, str):
            return self.schemas.get(ref.rsplit("/", 1)[-1], schema)
        return schema

    def build(self, routes: Routes, document: openapi.OpenAPI) -> openapi.OpenAPI:
        """Describe `routes` in `document`, replacing whatever paths it carries."""

        paths: dict[str, openapi.PathItem] = {}
        operation_ids: dict[str, str] = {}

        for info in routes.describe():
            operation = info.definition.openapi
            if operation is None:
                continue

            template, declared = path_parameters(info.path)
            responses = operation.responses or DEFAULT_RESPONSES
            methods = documented_methods(info.definition)

            call = info.definition.call
            owner = inspection.callable_name(call.callable)
            contributed: list[openapi.Parameter] = []
            request_body: openapi.RequestBody | openapi.Reference | None = operation.request_body
            generated_body: openapi.RequestBody | None = None

            for param_info in call.parameters:
                binding = find_binding(param_info, owner)
                if not isinstance(binding, OpenAPIContributor):
                    continue
                piece = binding.to_openapi(param_info, self)
                contributed.extend(piece.parameters)
                if piece.request_body is not None and operation.request_body is None:
                    generated_body = merge_request_body(generated_body, piece.request_body, owner, self)
                    request_body = generated_body

            parameters = merge_parameters((*declared, *contributed), operation.parameters)

            for method in methods:
                base = operation.operation_id or info.name
                operation_id = base if len(methods) == 1 else f"{base}_{method}"
                previous = operation_ids.get(operation_id)
                if previous is not None:
                    raise DuplicateOperationError(
                        f"Operation id {operation_id!r} describes both {previous} and {method.upper()} {template}. "
                        f"Give one of them `operation_id=`."
                    )
                operation_ids[operation_id] = f"{method.upper()} {template}"

                described = dataclasses.replace(
                    operation,
                    operation_id=operation_id,
                    parameters=parameters,
                    request_body=request_body,
                    responses=responses,
                )
                item = paths.get(template, openapi.PathItem())
                if getattr(item, method, None) is not None:
                    raise DuplicateOperationError(
                        f"Two routes both describe {method.upper()} {template}, which a document cannot "
                        f"express. Give them distinct paths."
                    )
                paths[template] = item.with_operation(method, described)

        components = document.components or openapi.Components()
        if self.schemas:
            components = dataclasses.replace(
                components,
                schemas={**(components.schemas or {}), **self.schemas},
            )
        if components.schemas or components.security_schemes or components.parameters or components.responses:
            return dataclasses.replace(document, paths=paths, components=components)
        return dataclasses.replace(document, paths=paths)


@typing.runtime_checkable
class OpenAPIContributor(typing.Protocol):
    def to_openapi(self, param_info: ParamInfo, context: openapi.SchemaContext) -> openapi.Contribution: ...


def merge_request_body(
    existing: openapi.RequestBody | None,
    incoming: openapi.RequestBody,
    owner: str,
    builder: OpenAPIBuilder,
) -> openapi.RequestBody:
    if existing is None:
        return incoming
    existing_form = existing.content.get(FORM_MEDIA_TYPE) if existing.content else None
    incoming_form = incoming.content.get(FORM_MEDIA_TYPE) if incoming.content else None
    if existing_form is not None and incoming_form is not None:
        left = dict(builder.resolve(existing_form.schema or {}))
        right = dict(builder.resolve(incoming_form.schema or {}))
        properties = {**(left.get("properties") or {}), **(right.get("properties") or {})}
        required = list(dict.fromkeys([*(left.get("required") or ()), *(right.get("required") or ())]))
        schema: openapi.Schema = {"type": "object", "properties": properties, "required": required}
        return openapi.RequestBody(
            content={FORM_MEDIA_TYPE: openapi.MediaType(schema=schema)},
            required=existing.required or incoming.required,
        )
    raise DuplicateOperationError(f"{owner}() declares two request bodies.")


def build_document(
    routes: Routes,
    document: openapi.OpenAPI,
    binders: tuple[ModelBinder, ...] = DEFAULT_MODEL_BINDERS,
    namer: SchemaNamer = default_schema_namer,
) -> openapi.OpenAPI:
    return OpenAPIBuilder(binders, namer=namer).build(routes, document)
