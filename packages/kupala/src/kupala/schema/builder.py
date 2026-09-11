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
from kupala.dependencies import Binding, Factory, ParamInfo, find_binding, inspect_callable
from kupala.routing import RouteDefinition, Routes
from kupala.schema import openapi
from kupala.schema.responses import response_schemas

__all__ = [
    "DuplicateOperationError",
    "OpenAPIBuilder",
    "SchemaNamer",
    "UnsupportedSchemaError",
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
    """Raised when generated OpenAPI cannot describe an operation unambiguously."""


class UnsupportedSchemaError(ValueError):
    """Raised when an annotation cannot be represented as JSON Schema."""


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
    owner: str,
) -> tuple[openapi.Parameter | openapi.Reference, ...] | None:
    """The parameters a path declares, plus whatever its author declared beside them."""

    claimed = {
        (parameter.name, parameter.in_) for parameter in authored or () if isinstance(parameter, openapi.Parameter)
    }
    unique: dict[tuple[str, openapi.ParameterLocation], openapi.Parameter] = {}
    for parameter in generated:
        key = (parameter.name, parameter.in_)
        if key in claimed:
            continue
        existing = unique.get(key)
        if existing is not None and existing != parameter:
            raise DuplicateOperationError(
                f"{parameter.in_.value} parameter {parameter.name!r} has conflicting definitions "
                f"while describing {owner}()."
            )
        unique[key] = parameter
    generated = tuple(unique.values())

    if not authored:
        return generated or None

    return (*generated, *authored)


def merge_security_schemes(
    existing: typing.Mapping[str, openapi.SecurityScheme | openapi.Reference] | None,
    incoming: typing.Mapping[str, openapi.SecurityScheme | openapi.Reference],
    owner: str,
) -> dict[str, openapi.SecurityScheme | openapi.Reference]:
    """Merge named schemes without mutating either contribution."""

    merged = dict(existing or {})
    for name, scheme in incoming.items():
        if name in merged and merged[name] != scheme:
            raise ValueError(
                f"Security scheme {name!r} has conflicting definitions while describing {owner}. "
                f"Reuse the same definition or choose a distinct name."
            )
        merged[name] = scheme
    return merged


def merge_security_requirements(
    existing: openapi.SecurityRequirement | None,
    incoming: openapi.SecurityRequirement | None,
) -> dict[str, tuple[str, ...]] | None:
    """Combine two simultaneously required scheme mappings with stable scope order."""

    if not existing and not incoming:
        return None

    merged = {name: tuple(scopes) for name, scopes in (existing or {}).items()}
    for name, scopes in (incoming or {}).items():
        merged[name] = tuple(dict.fromkeys((*merged.get(name, ()), *scopes)))
    return merged


def merge_operation_security(
    required: openapi.SecurityRequirement | None,
    authored: typing.Sequence[openapi.SecurityRequirement] | None,
    inherited: typing.Sequence[openapi.SecurityRequirement] | None,
) -> typing.Sequence[openapi.SecurityRequirement] | None:
    """Add required bindings to every authored or document-level alternative."""

    if not required:
        return authored

    alternatives = authored if authored is not None else inherited
    if not alternatives:
        return (required,)
    return tuple(merge_security_requirements(alternative, required) or {} for alternative in alternatives)


def walk_dependency_bindings(
    parameters: tuple[ParamInfo, ...],
    owner: str,
    factories: list[Factory],
) -> typing.Iterator[tuple[ParamInfo, Binding]]:
    """Yield bindings in the dependency graph once per factory."""

    for param in parameters:
        binding = find_binding(param, owner)
        yield param, binding
        if not isinstance(binding, Factory) or binding in factories:
            continue

        factories.append(binding)
        dependency = inspect_callable(binding.factory)
        yield from walk_dependency_bindings(
            dependency.parameters,
            inspection.callable_name(dependency.callable),
            factories,
        )


def documented_methods(definition: RouteDefinition) -> tuple[str, ...]:
    """The methods of a definition worth documenting, in their OpenAPI spelling."""

    methods = tuple(
        dict.fromkeys(
            method.lower() if method.lower() in openapi.HTTP_METHODS else method for method in definition.methods
        )
    )
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
        self._reserved_schema_names: set[str] = set()

    def name_for(self, type_: type) -> str:
        if type_ in self.types:
            return self.types[type_]

        taken = set(self.schemas) | set(self.types.values()) | self._reserved_schema_names
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
        taken = set(self.schemas) | self._reserved_schema_names | {name}
        mapping: dict[str, str] = {}
        for def_name in defs:
            stored = def_name
            if stored in taken:
                qualified = f"{name}.{def_name}"
                stored = qualified
                suffix = 2
                while stored in taken:
                    stored = f"{qualified}.{suffix}"
                    suffix += 1
            mapping[def_name] = stored
            taken.add(stored)
        mapping.setdefault(name, name)

        self.schemas[name] = typing.cast(openapi.Schema, _rewrite_refs(root, mapping))
        for def_name, def_schema in defs.items():
            stored = mapping[def_name]
            self.schemas[stored] = typing.cast(openapi.Schema, _rewrite_refs(def_schema, mapping))
        return {"$ref": f"#/components/schemas/{name}"}

    def binder_for(self, type_: typing.Any) -> ModelBinder | None:
        return next((binder for binder in self.binders if binder.supports(type_)), None)

    def is_model(self, type_: typing.Any) -> bool:
        type_, _ = inspection.unwrap_annotation(type_)
        return self.binder_for(type_) is not None

    def schema_for(self, type_: typing.Any) -> openapi.Schema:
        type_, _ = inspection.unwrap_annotation(type_)
        binder = self.binder_for(type_)
        if binder is not None:
            if not isinstance(type_, type):
                raise UnsupportedSchemaError(f"Cannot describe {inspection.type_name(type_)} as a JSON Schema.")
            return self.register(type_, binder.schema(type_))

        scalar = SCALAR_SCHEMAS.get(type_)
        if scalar is not None:
            return scalar
        if isinstance(type_, type) and issubclass(type_, enum.Enum):
            values = [member.value for member in type_]
            json_type = {
                frozenset({str}): "string",
                frozenset({int}): "integer",
                frozenset({float}): "number",
                frozenset({int, float}): "number",
                frozenset({bool}): "boolean",
            }.get(frozenset(type(value) for value in values))
            if json_type is None:
                return {"enum": values}
            return {"type": json_type, "enum": values}

        origin = typing.get_origin(type_)
        args = typing.get_args(type_)
        if origin in (
            list,
            set,
            frozenset,
            collections.abc.Iterable,
            collections.abc.Sequence,
            collections.abc.Set,
        ):
            if len(args) != 1:
                raise UnsupportedSchemaError(
                    f"Cannot describe {inspection.type_name(type_)} as a JSON array; annotate its item type."
                )
            if origin in (set, frozenset, collections.abc.Set):
                return {"type": "array", "items": self.schema_for(args[0]), "uniqueItems": True}
            return {"type": "array", "items": self.schema_for(args[0])}
        if origin in (dict, collections.abc.Mapping, collections.abc.MutableMapping):
            if len(args) != 2 or args[0] is not str:
                raise UnsupportedSchemaError(
                    f"Cannot describe {inspection.type_name(type_)} as a JSON object; use str keys and a value type."
                )
            return {"type": "object", "additionalProperties": self.schema_for(args[1])}

        raise UnsupportedSchemaError(f"Cannot describe {inspection.type_name(type_)} as a JSON Schema.")

    def properties_of(self, type_: typing.Any) -> tuple[typing.Mapping[str, openapi.Schema], frozenset[str]]:
        type_, _ = inspection.unwrap_annotation(type_)
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

        components = document.components or openapi.Components()
        authored_schemas = components.schemas or {}
        conflict = next((name for name in self.schemas if name in authored_schemas), None)
        if conflict is not None:
            raise ValueError(f"Generated schema {conflict!r} conflicts with an authored component.")
        self._reserved_schema_names.update(authored_schemas)

        paths: dict[str, openapi.PathItem] = {}
        operation_ids: dict[str, str] = {}
        security_schemes: dict[str, openapi.SecurityScheme | openapi.Reference] = {}

        for info in routes.describe():
            operation = info.definition.openapi
            if operation is None:
                continue

            template, declared = path_parameters(info.path)
            methods = documented_methods(info.definition)

            call = info.definition.call
            inferred_responses = response_schemas(call.return_type, self)
            owner = inspection.callable_name(call.callable)
            contributed: list[openapi.Parameter] = []
            contributed_responses: openapi.Responses | None = None
            required_security: openapi.SecurityRequirement | None = None
            request_body: openapi.RequestBody | openapi.Reference | None = operation.request_body
            generated_body: openapi.RequestBody | None = None

            for param_info, binding in walk_dependency_bindings(call.parameters, owner, []):
                if not isinstance(binding, OpenAPIContributor):
                    continue
                piece = binding.to_openapi(param_info, self)
                contributed.extend(piece.parameters)
                if piece.security_schemes:
                    security_schemes = merge_security_schemes(security_schemes, piece.security_schemes, f"{owner}()")
                required_security = merge_security_requirements(required_security, piece.security)
                if piece.responses:
                    contributed_responses = merge_responses(contributed_responses, piece.responses)
                if piece.request_body is not None and operation.request_body is None:
                    generated_body = merge_request_body(generated_body, piece.request_body, owner, self)
                    request_body = generated_body

            parameters = merge_parameters((*declared, *contributed), operation.parameters, owner)
            responses: openapi.Responses = (
                dict(DEFAULT_RESPONSES) if inferred_responses is None and not operation.responses else {}
            )
            if contributed_responses is not None:
                responses = merge_responses(responses, contributed_responses)
            if inferred_responses is not None:
                responses = merge_responses(responses, inferred_responses)
            if operation.responses is not None:
                responses = merge_responses(responses, operation.responses)
            security = merge_operation_security(required_security, operation.security, document.security)

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
                    security=security,
                )
                item = paths.get(template, openapi.PathItem())
                existing = (
                    getattr(item, method)
                    if method in openapi.HTTP_METHODS
                    else (item.additional_operations or {}).get(method)
                )
                if existing is not None:
                    raise DuplicateOperationError(
                        f"Two routes both describe {method.upper()} {template}, which a document cannot "
                        f"express. Give them distinct paths."
                    )
                paths[template] = item.with_operation(method, described)

        if self.schemas:
            components = dataclasses.replace(
                components,
                schemas={**(components.schemas or {}), **self.schemas},
            )
        if security_schemes:
            components = dataclasses.replace(
                components,
                security_schemes=merge_security_schemes(
                    components.security_schemes,
                    security_schemes,
                    "the OpenAPI document",
                ),
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


def merge_responses(
    generated: openapi.Responses | None,
    authored: openapi.Responses,
) -> openapi.Responses:
    if generated is None:
        return dict(authored)

    merged = dict(generated)
    for status, response in authored.items():
        existing = merged.get(status)
        if isinstance(existing, openapi.Response) and isinstance(response, openapi.Response):
            merged[status] = dataclasses.replace(
                existing,
                summary=response.summary if response.summary is not None else existing.summary,
                description=response.description if response.description is not None else existing.description,
                headers=response.headers if response.headers is not None else existing.headers,
                content=response.content if response.content is not None else existing.content,
                links=response.links if response.links is not None else existing.links,
                extensions=response.extensions if response.extensions is not None else existing.extensions,
            )
        else:
            merged[status] = response
    return merged


def build_document(
    routes: Routes,
    document: openapi.OpenAPI,
    binders: tuple[ModelBinder, ...] = DEFAULT_MODEL_BINDERS,
    namer: SchemaNamer = default_schema_namer,
) -> openapi.OpenAPI:
    return OpenAPIBuilder(binders, namer=namer).build(routes, document)
