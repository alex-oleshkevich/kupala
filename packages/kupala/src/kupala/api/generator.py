"""Turn a route tree into an OpenAPI document."""

import dataclasses
import typing

from starlette.convertors import Convertor
from starlette.routing import compile_path

from kupala import openapi
from kupala.routing import RouteDefinition, Routes

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


def build_document(routes: Routes, document: openapi.OpenAPI) -> openapi.OpenAPI:
    """Describe `routes` in `document`, replacing whatever paths it carries."""

    paths: dict[str, openapi.PathItem] = {}
    operation_ids: dict[str, str] = {}

    for info in routes.describe():
        operation = info.definition.openapi
        if operation is None:
            continue

        template, parameters = path_parameters(info.path)
        methods = documented_methods(info.definition)

        for method in methods:
            # one definition may answer several methods, and each needs an id of its own — including
            # when the author named it, or naming a `get_or_post` route would collide with itself
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
                parameters=parameters or None,
                responses=operation.responses or DEFAULT_RESPONSES,
            )
            item = paths.get(template, openapi.PathItem())
            if getattr(item, method, None) is not None:
                raise DuplicateOperationError(
                    f"Two routes both describe {method.upper()} {template}, which a document cannot "
                    f"express. Give them distinct paths."
                )
            paths[template] = item.with_operation(method, described)

    return dataclasses.replace(document, paths=paths)
