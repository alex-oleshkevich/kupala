"""The OpenAPI 3.1 document model.

Every object the specification defines has a dataclass here, and `to_dict` renders any of them into
the JSON structure a tool consumes. Objects are frozen, so a document can be built once and shared
between the route walk that produces it, the endpoint that serves it, and the CLI that exports it.

The one object deliberately not modelled is the Schema Object. OpenAPI 3.1 schemas are plain JSON
Schema 2020-12 documents, which no fixed set of fields can describe, and which pydantic and msgspec
both already emit as mappings. `Discriminator` and `XML` are absent for the same reason: in 3.1 they
are schema keywords, so they live inside those mappings rather than beside them.

Validation is deliberately partial. It covers the mistakes tooling accepts and then quietly ignores —
an incomplete security scheme, an OAuth2 flow with no URL, a 3.1-only document claiming 3.0 — and
leaves the ambiguous ones alone, because an error a reader can see in the output does not need a
second report here.
"""

import collections.abc
import dataclasses
import enum
import typing

__all__ = [
    "Callback",
    "Components",
    "Contact",
    "Encoding",
    "Example",
    "Extensions",
    "ExternalDocumentation",
    "Header",
    "Info",
    "License",
    "Link",
    "MediaType",
    "OAuthFlow",
    "OAuthFlows",
    "OpenAPI",
    "Operation",
    "Parameter",
    "ParameterLocation",
    "ParameterStyle",
    "PathItem",
    "Reference",
    "RequestBody",
    "Response",
    "Responses",
    "Schema",
    "SecurityRequirement",
    "SecurityScheme",
    "SecuritySchemeType",
    "Server",
    "ServerVariable",
    "Tag",
    "to_dict",
]

# `x-` prefixed members, which every object below the document root may carry
type Extensions = typing.Mapping[str, typing.Any]

# a JSON Schema 2020-12 document; `{}` stands in for the `true` schema, so no bool member is needed
type Schema = typing.Mapping[str, typing.Any]

# scheme name -> the scopes it must grant; an empty sequence for schemes that have none
type SecurityRequirement = typing.Mapping[str, typing.Sequence[str]]

# status code, a wildcard such as "5XX", or "default"
type Responses = typing.Mapping[str, Response | Reference]

# runtime expression -> the request the API sends out
type Callback = typing.Mapping[str, PathItem | Reference]


class ParameterLocation(enum.StrEnum):
    QUERY = "query"
    HEADER = "header"
    PATH = "path"
    COOKIE = "cookie"


class ParameterStyle(enum.StrEnum):
    MATRIX = "matrix"
    LABEL = "label"
    FORM = "form"
    SIMPLE = "simple"
    SPACE_DELIMITED = "spaceDelimited"
    PIPE_DELIMITED = "pipeDelimited"
    DEEP_OBJECT = "deepObject"


class SecuritySchemeType(enum.StrEnum):
    API_KEY = "apiKey"
    HTTP = "http"
    MUTUAL_TLS = "mutualTLS"
    OAUTH2 = "oauth2"
    OPEN_ID_CONNECT = "openIdConnect"


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Contact:
    name: str | None = None
    url: str | None = None
    email: str | None = None
    extensions: Extensions | None = None


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class License:
    name: str
    # an SPDX expression, which 3.1 accepts instead of `url`
    identifier: str | None = None
    url: str | None = None
    extensions: Extensions | None = None


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Info:
    title: str
    version: str
    summary: str | None = None
    description: str | None = None
    terms_of_service: str | None = None
    contact: Contact | None = None
    license: License | None = None
    extensions: Extensions | None = None


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class ServerVariable:
    default: str
    enum: typing.Sequence[str] | None = None
    description: str | None = None
    extensions: Extensions | None = None


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Server:
    url: str
    description: str | None = None
    variables: typing.Mapping[str, ServerVariable] | None = None
    extensions: Extensions | None = None


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class ExternalDocumentation:
    url: str
    description: str | None = None
    extensions: Extensions | None = None


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Tag:
    name: str
    description: str | None = None
    external_docs: ExternalDocumentation | None = None
    extensions: Extensions | None = None


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Reference:
    # the one object the specification gives no extensions, so it carries no `extensions` member
    ref: str
    summary: str | None = None
    description: str | None = None


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Example:
    summary: str | None = None
    description: str | None = None
    # an example whose value is literally `null` cannot be spelled: `None` means absent everywhere here
    value: typing.Any = None
    external_value: str | None = None
    extensions: Extensions | None = None


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Header:
    """A header, in a response or in a multipart encoding.

    A `Parameter` without `name` and `in`, which the position already fixes, and without
    `allow_empty_value` and `allow_reserved`, which the specification defines for query strings only.
    """

    description: str | None = None
    required: bool | None = None
    deprecated: bool | None = None
    style: ParameterStyle | None = None
    explode: bool | None = None
    schema: Schema | None = None
    example: typing.Any = None
    examples: typing.Mapping[str, Example | Reference] | None = None
    content: typing.Mapping[str, MediaType] | None = None
    extensions: Extensions | None = None


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Encoding:
    content_type: str | None = None
    headers: typing.Mapping[str, Header | Reference] | None = None
    style: ParameterStyle | None = None
    explode: bool | None = None
    allow_reserved: bool | None = None
    extensions: Extensions | None = None


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class MediaType:
    schema: Schema | None = None
    example: typing.Any = None
    examples: typing.Mapping[str, Example | Reference] | None = None
    encoding: typing.Mapping[str, Encoding] | None = None
    extensions: Extensions | None = None


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class RequestBody:
    content: typing.Mapping[str, MediaType]
    description: str | None = None
    required: bool | None = None
    extensions: Extensions | None = None


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Link:
    operation_ref: str | None = None
    operation_id: str | None = None
    parameters: typing.Mapping[str, typing.Any] | None = None
    request_body: typing.Any = None
    description: str | None = None
    server: Server | None = None
    extensions: Extensions | None = None


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Response:
    description: str
    headers: typing.Mapping[str, Header | Reference] | None = None
    content: typing.Mapping[str, MediaType] | None = None
    links: typing.Mapping[str, Link | Reference] | None = None
    extensions: Extensions | None = None


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Parameter:
    name: str
    in_: ParameterLocation
    description: str | None = None
    required: bool | None = None
    deprecated: bool | None = None
    allow_empty_value: bool | None = None
    style: ParameterStyle | None = None
    explode: bool | None = None
    allow_reserved: bool | None = None
    schema: Schema | None = None
    example: typing.Any = None
    examples: typing.Mapping[str, Example | Reference] | None = None
    content: typing.Mapping[str, MediaType] | None = None
    extensions: Extensions | None = None

    def __post_init__(self) -> None:
        # a path parameter that is not required describes a route that cannot exist, and tools reject it
        if self.in_ is ParameterLocation.PATH and not self.required:
            raise ValueError(f"Path parameter {self.name!r} must be required.")


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class OAuthFlow:
    # scope name -> what it permits; required even when the flow defines no scopes
    scopes: typing.Mapping[str, str]
    authorization_url: str | None = None
    token_url: str | None = None
    refresh_url: str | None = None
    extensions: Extensions | None = None


# which URLs each flow cannot work without, checked because a flow object cannot tell which slot it fills
OAUTH_FLOW_REQUIREMENTS: typing.Final[typing.Mapping[str, tuple[str, ...]]] = {
    "implicit": ("authorization_url",),
    "password": ("token_url",),
    "client_credentials": ("token_url",),
    "authorization_code": ("authorization_url", "token_url"),
}


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class OAuthFlows:
    implicit: OAuthFlow | None = None
    password: OAuthFlow | None = None
    client_credentials: OAuthFlow | None = None
    authorization_code: OAuthFlow | None = None
    extensions: Extensions | None = None

    def __post_init__(self) -> None:
        for slot, required in OAUTH_FLOW_REQUIREMENTS.items():
            flow: OAuthFlow | None = getattr(self, slot)
            if flow is None:
                continue

            missing = [name for name in required if getattr(flow, name) is None]
            if missing:
                listed = ", ".join(repr(name) for name in missing)
                raise ValueError(f"OAuth2 {slot} flow is missing {listed}.")


# what each scheme type cannot be described without; an empty tuple means the type alone is enough
SECURITY_SCHEME_REQUIREMENTS: typing.Final[typing.Mapping[SecuritySchemeType, tuple[str, ...]]] = {
    SecuritySchemeType.API_KEY: ("name", "in_"),
    SecuritySchemeType.HTTP: ("scheme",),
    SecuritySchemeType.MUTUAL_TLS: (),
    SecuritySchemeType.OAUTH2: ("flows",),
    SecuritySchemeType.OPEN_ID_CONNECT: ("open_id_connect_url",),
}


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class SecurityScheme:
    type: SecuritySchemeType
    description: str | None = None
    name: str | None = None
    in_: ParameterLocation | None = None
    scheme: str | None = None
    bearer_format: str | None = None
    flows: OAuthFlows | None = None
    open_id_connect_url: str | None = None
    extensions: Extensions | None = None

    def __post_init__(self) -> None:
        # most tooling ignores an incomplete scheme rather than reporting it, so it fails here instead
        missing = [name for name in SECURITY_SCHEME_REQUIREMENTS[self.type] if getattr(self, name) is None]
        if missing:
            listed = ", ".join(repr(name) for name in missing)
            raise ValueError(f"Security scheme of type {self.type.value!r} is missing {listed}.")


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Operation:
    """One method of one path.

    A route decorator fills in what only the author knows — tags, summary, security — and the
    generator adds `parameters`, `request_body` and `responses` from the endpoint signature with
    `dataclasses.replace`. Every field is optional so both halves can build one independently.
    """

    tags: typing.Sequence[str] | None = None
    summary: str | None = None
    description: str | None = None
    external_docs: ExternalDocumentation | None = None
    operation_id: str | None = None
    parameters: typing.Sequence[Parameter | Reference] | None = None
    request_body: RequestBody | Reference | None = None
    responses: Responses | None = None
    callbacks: typing.Mapping[str, Callback | Reference] | None = None
    deprecated: bool | None = None
    security: typing.Sequence[SecurityRequirement] | None = None
    servers: typing.Sequence[Server] | None = None
    extensions: Extensions | None = None


# the operation slots a path item has, which is also what `with_operation` accepts
HTTP_METHODS: typing.Final = ("get", "put", "post", "delete", "options", "head", "patch", "trace")


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class PathItem:
    ref: str | None = None
    summary: str | None = None
    description: str | None = None
    get: Operation | None = None
    put: Operation | None = None
    post: Operation | None = None
    delete: Operation | None = None
    options: Operation | None = None
    head: Operation | None = None
    patch: Operation | None = None
    trace: Operation | None = None
    servers: typing.Sequence[Server] | None = None
    parameters: typing.Sequence[Parameter | Reference] | None = None
    extensions: Extensions | None = None

    def with_operation(self, method: str, operation: Operation) -> typing.Self:
        """Return a copy carrying `operation` under `method`, which routes are documented one at a time."""

        slot = method.lower()
        if slot not in HTTP_METHODS:
            listed = ", ".join(name.upper() for name in HTTP_METHODS)
            raise ValueError(f"OpenAPI path items describe no {method!r} operation. Use one of: {listed}.")

        # the check above is what makes this sound: `replace` types each keyword against one named
        # field, which cannot describe a field chosen at runtime
        changes: typing.Any = {slot: operation}
        return dataclasses.replace(self, **changes)


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Components:
    schemas: typing.Mapping[str, Schema] | None = None
    responses: typing.Mapping[str, Response | Reference] | None = None
    parameters: typing.Mapping[str, Parameter | Reference] | None = None
    examples: typing.Mapping[str, Example | Reference] | None = None
    request_bodies: typing.Mapping[str, RequestBody | Reference] | None = None
    headers: typing.Mapping[str, Header | Reference] | None = None
    security_schemes: typing.Mapping[str, SecurityScheme | Reference] | None = None
    links: typing.Mapping[str, Link | Reference] | None = None
    callbacks: typing.Mapping[str, Callback | Reference] | None = None
    path_items: typing.Mapping[str, PathItem | Reference] | None = None
    extensions: Extensions | None = None


SUPPORTED_OPENAPI_VERSION: typing.Final = "3.1"


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class OpenAPI:
    # declared first so it serializes first, which is where every published document carries it
    openapi: str = "3.1.1"
    info: Info
    json_schema_dialect: str | None = None
    servers: typing.Sequence[Server] | None = None
    paths: typing.Mapping[str, PathItem] | None = None
    webhooks: typing.Mapping[str, PathItem | Reference] | None = None
    components: Components | None = None
    security: typing.Sequence[SecurityRequirement] | None = None
    tags: typing.Sequence[Tag] | None = None
    external_docs: ExternalDocumentation | None = None
    extensions: Extensions | None = None

    def __post_init__(self) -> None:
        # this module models 3.1 only: `webhooks`, `Info.summary`, `License.identifier` and mutualTLS
        # are all invalid under 3.0, and a document that claims 3.0 while carrying them is silently wrong
        if not self.openapi.startswith(f"{SUPPORTED_OPENAPI_VERSION}."):
            raise ValueError(
                f"Unsupported OpenAPI version {self.openapi!r}. "
                f"This document model describes {SUPPORTED_OPENAPI_VERSION}."
            )

        for path in self.paths or ():
            if not path.startswith("/"):
                raise ValueError(f"Path {path!r} must start with '/'.")


# spellings `to_dict` cannot reach by casing alone
FIELD_ALIASES: typing.Final[typing.Mapping[str, str]] = {
    "in_": "in",
    "ref": "$ref",
}


def camelize(name: str) -> str:
    """Spell a field name the way the specification does."""

    head, *rest = name.split("_")
    return head + "".join(word[:1].upper() + word[1:] for word in rest)


def to_dict(value: typing.Any) -> typing.Any:
    """Render any object from this module into its JSON form.

    Absent members are those set to `None`, so an empty collection stays in the output — the
    difference matters for members the specification requires even when they hold nothing, such as
    `OAuthFlow.scopes`.
    """

    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return _object_to_dict(value)

    if isinstance(value, enum.Enum):
        return value.value

    if isinstance(value, collections.abc.Mapping):
        return {str(key): to_dict(item) for key, item in value.items()}

    # a string is a Sequence, and bytes have no JSON form, so neither is walked
    if isinstance(value, str | bytes):
        return value

    if isinstance(value, collections.abc.Sequence):
        return [to_dict(item) for item in value]

    return value


def _object_to_dict(instance: typing.Any) -> dict[str, typing.Any]:
    result: dict[str, typing.Any] = {}
    extensions: Extensions = {}

    for field in dataclasses.fields(instance):
        member = getattr(instance, field.name)
        if member is None:
            continue

        if field.name == "extensions":
            extensions = member
            continue

        result[FIELD_ALIASES.get(field.name, camelize(field.name))] = to_dict(member)

    for key, member in extensions.items():
        # an unprefixed key is not an extension: tooling either ignores it or rejects the document
        if not key.startswith("x-"):
            raise ValueError(f"Extension key {key!r} must start with 'x-'.")

        result[key] = to_dict(member)

    return result
