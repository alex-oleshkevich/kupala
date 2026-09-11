import dataclasses
import typing

from kupala.responses import JSONResponse
from kupala.schema import openapi

JSON_MEDIA_TYPE = "application/json"


@dataclasses.dataclass(frozen=True, slots=True)
class ResponseSpec:
    body_type: typing.Any
    status_codes: tuple[int, ...]
    headers_type: typing.Any


def parse_response(return_type: typing.Any) -> ResponseSpec | None:
    if typing.get_origin(return_type) is not JSONResponse:
        return None

    args = typing.get_args(return_type)
    if len(args) != 3:
        return None

    body_type, status_type, headers_type = args
    if typing.get_origin(status_type) is not typing.Literal:
        raise ValueError("Response status must be annotated with Literal[...].")

    status_codes = typing.get_args(status_type)
    if not status_codes or any(
        not isinstance(status, int) or isinstance(status, bool) or not 100 <= status <= 599 for status in status_codes
    ):
        raise ValueError("Response status literals must be HTTP status codes.")

    return ResponseSpec(body_type, tuple(status_codes), headers_type)


def response_schemas(return_type: typing.Any, context: openapi.SchemaContext) -> openapi.Responses | None:
    spec = parse_response(return_type)
    if spec is None:
        return None

    headers = headers_schema(spec.headers_type, context)
    response = openapi.Response(
        description="Successful response.",
        headers=headers,
        content={
            JSON_MEDIA_TYPE: openapi.MediaType(
                schema=context.schema_for(spec.body_type),
            ),
        },
    )
    return {str(status): response for status in spec.status_codes}


def headers_schema(
    type_: typing.Any,
    context: openapi.SchemaContext,
) -> typing.Mapping[str, openapi.Header] | None:
    if not typing.is_typeddict(type_):
        return None

    annotations = typing.get_type_hints(type_, include_extras=True)
    required = type_.__required_keys__
    return {
        name: openapi.Header(required=name in required, schema=context.schema_for(annotation))
        for name, annotation in annotations.items()
    }
