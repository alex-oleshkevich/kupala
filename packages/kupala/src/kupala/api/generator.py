"""Turn a route tree into an OpenAPI document."""

import dataclasses
import typing

from starlette.convertors import Convertor
from starlette.routing import compile_path

from kupala import openapi
from kupala.routing import RouteDefinition, Routes, endpoint_name, join_namespace, join_path

__all__ = ["DuplicateOperationError", "build_document", "path_parameters"]

# Starlette's convertors, as the schema each one guarantees the endpoint will receive. Keyed by class
# because a convertor carries no name, and the class is not the spelling: `{id:int}` is IntegerConvertor
CONVERTOR_SCHEMAS: typing.Final[typing.Mapping[str, openapi.Schema]] = {
    "StringConvertor": {"type": "string"},
    "PathConvertor": {"type": "string", "format": "path"},
    "IntegerConvertor": {"type": "integer"},
    "FloatConvertor": {"type": "number"},
    "UUIDConvertor": {"type": "string", "format": "uuid"},
}

DEFAULT_RESPONSES: typing.Final[openapi.Responses] = {
    "200": openapi.Response(description="Successful response."),
}


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


def documented_methods(definition: RouteDefinition) -> tuple[str, ...]:
    """The methods of a definition worth documenting, lowercased for a path item."""

    methods = tuple(dict.fromkeys(method.lower() for method in definition.methods))
    # `get()` registers HEAD alongside GET, and a HEAD entry beside its GET only repeats it
    if "get" in methods:
        methods = tuple(method for method in methods if method != "head")
    return methods


def walk(
    group: Routes,
    prefix: str = "",
    namespace: str = "",
) -> typing.Iterator[tuple[str, str, RouteDefinition]]:
    """Yield every documented route as its resolved path, route name and definition.

    This repeats the prefix and namespace joining `Routes.compile` does, because a compiled route
    keeps neither its definition nor the group it came from. Mounts and hosts are skipped: they
    dispatch to another application, which describes itself or does not.
    """

    prefix = join_path(prefix, group.prefix)
    namespace = join_namespace(namespace, group.namespace)

    for definition in group.definitions:
        if isinstance(definition, RouteDefinition) and definition.openapi is not None:
            name = join_namespace(namespace, definition.name or endpoint_name(definition.fn))
            yield join_path(prefix, definition.path), name, definition

    for child in group._children:
        yield from walk(child, prefix, namespace)


def build_document(routes: Routes, document: openapi.OpenAPI) -> openapi.OpenAPI:
    """Describe `routes` in `document`, replacing whatever paths it carries."""

    paths: dict[str, openapi.PathItem] = {}
    operation_ids: dict[str, str] = {}

    for path, name, definition in walk(routes):
        assert definition.openapi is not None  # walk() yields only documented routes
        template, parameters = path_parameters(path)
        methods = documented_methods(definition)

        for method in methods:
            # one definition may answer several methods, and each needs an id of its own — including
            # when the author named it, or naming a `get_or_post` route would collide with itself
            base = definition.openapi.operation_id or name
            operation_id = base if len(methods) == 1 else f"{base}_{method}"
            previous = operation_ids.get(operation_id)
            if previous is not None:
                raise DuplicateOperationError(
                    f"Operation id {operation_id!r} describes both {previous} and {method.upper()} {template}. "
                    f"Give one of them `operation_id=`."
                )
            operation_ids[operation_id] = f"{method.upper()} {template}"

            operation = dataclasses.replace(
                definition.openapi,
                operation_id=operation_id,
                parameters=parameters or None,
                responses=definition.openapi.responses or DEFAULT_RESPONSES,
            )
            item = paths.get(template, openapi.PathItem())
            # a documented path drops the convertor, so `/u/{id:int}` and `/u/{id}` route apart and
            # document the same. Overwriting would lose one operation and describe the wrong endpoint
            if getattr(item, method) is not None:
                raise DuplicateOperationError(
                    f"Two routes both describe {method.upper()} {template}, which a document cannot "
                    f"express. Give them distinct paths."
                )
            paths[template] = item.with_operation(method, operation)

    return dataclasses.replace(document, paths=paths)
