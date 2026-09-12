import base64
import dataclasses
import re
import string
import typing
from email.utils import quote

from starlette.requests import HTTPConnection, cookie_parser

from kupala import inspection
from kupala.dependencies import (
    CallableInfo,
    CircularDependencyError,
    CompileContext,
    Factory,
    InvalidDependencyError,
    InvocationContext,
    ParamInfo,
    Resolver,
    compile_call_plan,
    inspect_callable,
    resolve_arguments,
    run_callable,
)
from kupala.errors import (
    BadRequestError,
    BaseHTTPError,
    InvalidCredentialsError,
    NotAuthenticatedError,
    NotAuthorizedError,
)
from kupala.schema import openapi

__all__ = ["APIKey", "BasicAuth", "BasicCredentials", "Bearer", "Identity", "OAuth2"]

_CONTROL_CHARACTERS = re.compile(r"[\x00-\x1f\x7f]")
_COMPONENT_NAME = re.compile(r"[A-Za-z0-9._-]+", re.ASCII)
_HTTP_TOKEN = re.compile(r"[!#$%&'*+\-.^_`|~0-9A-Za-z]+", re.ASCII)
_BEARER_TOKEN_CHARACTERS = frozenset(string.ascii_letters + string.digits + "-._~+/")
_OAUTH_SCOPE = re.compile(r"[\x21\x23-\x5b\x5d-\x7e]+", re.ASCII)
_API_KEY_LOCATIONS: typing.Final = {
    "header": openapi.ParameterLocation.HEADER,
    "query": openapi.ParameterLocation.QUERY,
    "cookie": openapi.ParameterLocation.COOKIE,
}


@dataclasses.dataclass(frozen=True, slots=True)
class Identity[T]:
    """An authenticated principal and the scopes granted to it."""

    principal: T
    scopes: frozenset[str] = dataclasses.field(default_factory=frozenset)


@dataclasses.dataclass(frozen=True, slots=True)
class BasicCredentials:
    """A username and password extracted from HTTP Basic credentials."""

    username: str
    password: str = dataclasses.field(repr=False)


def _compile_authenticate[Credential, T](
    callback: typing.Callable[..., Identity[T] | typing.Awaitable[Identity[T]]],
    context: CompileContext,
    param: ParamInfo,
    challenge: str | None,
    *,
    credential_type: type[Credential],
    scheme: str,
) -> typing.Callable[[Credential, InvocationContext], typing.Awaitable[Identity[T]]]:
    info = inspect_callable(callback)
    owner = inspection.callable_name(callback)
    if not info.parameters:
        raise InvalidDependencyError(f"{scheme} authenticator {owner}() must declare a first credential parameter.")

    credential = info.parameters[0]
    if credential.type is not credential_type or credential.optional:
        raise InvalidDependencyError(
            f"{scheme} authenticator {owner}() first credential parameter must be a required "
            f"{inspection.type_name(credential_type)}."
        )

    principal_type = typing.get_args(param.type)[0]
    expected_type = f"Identity[{inspection.type_name(principal_type)}]"
    return_type, _ = inspection.unwrap_annotation(info.return_type)
    if return_type != param.type:
        raise InvalidDependencyError(f"{scheme} authenticator {owner}() must return {expected_type}.")

    marker = Factory(callback)
    if marker in context.chain:
        path = " -> ".join(inspection.callable_name(entry.factory) for entry in (*context.chain, marker))
        raise CircularDependencyError(
            f"Circular dependency detected: {path}. An authenticator cannot depend on itself."
        )

    plan = compile_call_plan(callback, context.enter(marker), provided_parameter=credential.name)

    async def authenticate(credential_value: Credential, invocation: InvocationContext) -> Identity[T]:
        arguments = await resolve_arguments(plan, invocation)
        arguments[credential.name] = credential_value
        try:
            value = await run_callable(plan.callable, arguments)
        except InvalidCredentialsError as exc:
            if challenge is None:
                raise

            headers = {
                name: header_value
                for name, header_value in (exc.headers or {}).items()
                if name.lower() != "www-authenticate"
            }
            exc.headers = {**headers, "WWW-Authenticate": challenge}
            raise

        if not isinstance(value, Identity):
            raise InvalidDependencyError(
                f"{scheme} authenticator {owner}() returned {type(value).__name__}, expected {expected_type}."
            )
        return value

    return authenticate


def _split_authorization(value: str) -> tuple[str, str]:
    scheme = value.split(maxsplit=1)[0].lower() if value else ""
    prefix, separator, credentials = value.partition(" ")
    if not separator or prefix.lower() != scheme:
        return scheme, ""
    return scheme, credentials.lstrip(" ")


def _decode_basic(value: str) -> BasicCredentials | None:
    try:
        user_pass = base64.b64decode(value, validate=True).decode()
    except ValueError:
        return None

    username, separator, password = user_pass.partition(":")
    if not separator or _CONTROL_CHARACTERS.search(user_pass) is not None:
        return None
    return BasicCredentials(username, password)


@dataclasses.dataclass(frozen=True, slots=True, eq=False)
class APIKey[T = typing.Never]:
    """Read an API key from one explicit HTTP header, query parameter, or cookie."""

    name: str
    key_name: str
    location: typing.Literal["header", "query", "cookie"]
    authenticate: typing.Callable[..., Identity[T] | typing.Awaitable[Identity[T]]] | None = None
    error: typing.Callable[[str], BaseHTTPError] = NotAuthorizedError

    def __post_init__(self) -> None:
        if _COMPONENT_NAME.fullmatch(self.name) is None:
            raise ValueError("APIKey name must contain only letters, digits, dots, hyphens, and underscores.")
        if self.location not in _API_KEY_LOCATIONS:
            raise ValueError("APIKey location must be 'header', 'query', or 'cookie'.")
        if (
            not self.key_name
            or not self.key_name.isprintable()
            or (self.location != "query" and _HTTP_TOKEN.fullmatch(self.key_name) is None)
        ):
            raise ValueError("APIKey key_name is not valid for its location.")

    def _validate_parameter(self, param: ParamInfo) -> None:
        if self.authenticate is None:
            if param.type is not str or param.optional:
                raise InvalidDependencyError(f"APIKey parameter {param.name!r} must be a required str.")
            return

        if typing.get_origin(param.type) is not Identity or len(typing.get_args(param.type)) != 1 or param.optional:
            raise InvalidDependencyError(
                f"Authenticated APIKey parameter {param.name!r} must be a required Identity[T]."
            )

    def _values(self, connection: HTTPConnection) -> list[str]:
        if self.location == "header":
            return connection.headers.getlist(self.key_name)

        if self.location == "query":
            return connection.query_params.getlist(self.key_name)

        values: list[str] = []
        for header in connection.headers.getlist("cookie"):
            for chunk in header.split(";"):
                cookie = cookie_parser(chunk)
                if self.key_name in cookie:
                    values.append(cookie[self.key_name])

        return values

    def dependency_info(self) -> CallableInfo[..., typing.Any] | None:
        if self.authenticate is None:
            return None

        info = inspect_callable(self.authenticate)
        return dataclasses.replace(info, parameters=info.parameters[1:])

    def compile(self, context: CompileContext, param: ParamInfo) -> Resolver:
        self._validate_parameter(param)
        authenticate = None
        if self.authenticate is not None:
            authenticate = _compile_authenticate(
                self.authenticate,
                context,
                param,
                None,
                credential_type=str,
                scheme="APIKey",
            )

        async def resolve(context: InvocationContext) -> object:
            connection = await context.resolve(HTTPConnection)
            if connection.scope["type"] != "http":
                raise InvalidDependencyError("API keys can only be resolved for HTTP requests.")

            if self in context.cache:
                return context.cache[self]

            values = self._values(connection)
            if len(values) > 1:
                raise BadRequestError("Multiple API keys were supplied.")

            if not values or not values[0]:
                raise self.error("API key is required.")

            key = values[0]
            try:
                resolved = key if authenticate is None else await authenticate(key, context)
            except InvalidCredentialsError:
                raise self.error("Invalid API key.") from None

            context.cache[self] = resolved
            return resolved

        return resolve

    def to_openapi(self, param: ParamInfo, _context: openapi.SchemaContext) -> openapi.Contribution:
        self._validate_parameter(param)
        return openapi.Contribution(
            security_schemes={
                self.name: openapi.SecurityScheme(
                    type=openapi.SecuritySchemeType.API_KEY,
                    name=self.key_name,
                    in_=_API_KEY_LOCATIONS[self.location],
                )
            },
            security={self.name: ()},
        )


@dataclasses.dataclass(frozen=True, slots=True, eq=False)
class BasicAuth[T = typing.Never]:
    """Read HTTP Basic credentials using an explicit challenge realm."""

    realm: str
    name: str = "basic"
    authenticate: typing.Callable[..., Identity[T] | typing.Awaitable[Identity[T]]] | None = None

    def __post_init__(self) -> None:
        if _COMPONENT_NAME.fullmatch(self.name) is None:
            raise ValueError("BasicAuth name must contain only letters, digits, dots, hyphens, and underscores.")
        if not all(char.isascii() and char.isprintable() for char in self.realm):
            raise ValueError("BasicAuth realm must contain only printable ASCII characters.")

    def _validate_parameter(self, param: ParamInfo) -> None:
        if self.authenticate is None:
            if param.type is not BasicCredentials or param.optional:
                raise InvalidDependencyError(f"BasicAuth parameter {param.name!r} must be required BasicCredentials.")
            return

        if typing.get_origin(param.type) is not Identity or len(typing.get_args(param.type)) != 1 or param.optional:
            raise InvalidDependencyError(
                f"Authenticated BasicAuth parameter {param.name!r} must be a required Identity[T]."
            )

    def _challenge(self) -> str:
        return f'Basic realm="{quote(self.realm)}", charset="UTF-8"'

    def dependency_info(self) -> CallableInfo[..., typing.Any] | None:
        if self.authenticate is None:
            return None
        info = inspect_callable(self.authenticate)
        return dataclasses.replace(info, parameters=info.parameters[1:])

    def compile(self, context: CompileContext, param: ParamInfo) -> Resolver:
        self._validate_parameter(param)
        challenge = self._challenge()
        authenticate = None
        if self.authenticate is not None:
            authenticate = _compile_authenticate(
                self.authenticate,
                context,
                param,
                challenge,
                credential_type=BasicCredentials,
                scheme="BasicAuth",
            )

        async def resolve(context: InvocationContext) -> object:
            connection = await context.resolve(HTTPConnection)
            if connection.scope["type"] != "http":
                raise InvalidDependencyError("Basic credentials can only be resolved for HTTP requests.")
            if self in context.cache:
                return context.cache[self]

            values = connection.headers.getlist("authorization")
            headers = {"WWW-Authenticate": challenge}
            if not values:
                raise NotAuthenticatedError("Basic credentials are required.", headers=headers)
            if len(values) != 1:
                raise InvalidCredentialsError("Invalid Basic credentials.", headers=headers)

            value = values[0].strip(" \t")
            scheme, encoded = _split_authorization(value)
            if scheme and scheme != "basic":
                raise NotAuthenticatedError("Basic credentials are required.", headers=headers)

            credentials = _decode_basic(encoded)
            if credentials is None:
                raise InvalidCredentialsError("Invalid Basic credentials.", headers=headers)
            resolved = credentials if authenticate is None else await authenticate(credentials, context)
            context.cache[self] = resolved
            return resolved

        return resolve

    def to_openapi(self, param: ParamInfo, _context: openapi.SchemaContext) -> openapi.Contribution:
        self._validate_parameter(param)
        return openapi.Contribution(
            security_schemes={
                self.name: openapi.SecurityScheme(
                    type=openapi.SecuritySchemeType.HTTP,
                    scheme="basic",
                )
            },
            security={self.name: ()},
        )


@dataclasses.dataclass(frozen=True, slots=True, eq=False)
class Bearer[T = typing.Never]:
    """Read an HTTP Bearer credential using an explicit challenge realm."""

    realm: str
    name: str = "bearer"
    bearer_format: str | None = None
    authenticate: typing.Callable[..., Identity[T] | typing.Awaitable[Identity[T]]] | None = None

    def __post_init__(self) -> None:
        if _COMPONENT_NAME.fullmatch(self.name) is None:
            raise ValueError("Bearer name must contain only letters, digits, dots, hyphens, and underscores.")
        if not all(char.isascii() and char.isprintable() for char in self.realm):
            raise ValueError("Bearer realm must contain only printable ASCII characters.")

    def _validate_parameter(self, param: ParamInfo) -> None:
        if self.authenticate is None:
            if param.type is not str or param.optional:
                raise InvalidDependencyError(f"Bearer parameter {param.name!r} must be a required str.")
            return

        if typing.get_origin(param.type) is not Identity or len(typing.get_args(param.type)) != 1 or param.optional:
            raise InvalidDependencyError(
                f"Authenticated Bearer parameter {param.name!r} must be a required Identity[T]."
            )

    def _challenge(self, error: str | None = None, scope: str | None = None) -> str:
        values = [f'realm="{quote(self.realm)}"']
        if error is not None:
            values.append(f'error="{error}"')

        if scope is not None:
            values.append(f'scope="{quote(scope)}"')

        return f"Bearer {', '.join(values)}"

    def dependency_info(self) -> CallableInfo[..., typing.Any] | None:
        if self.authenticate is None:
            return None
        info = inspect_callable(self.authenticate)
        return dataclasses.replace(info, parameters=info.parameters[1:])

    def compile(self, context: CompileContext, param: ParamInfo) -> Resolver:
        self._validate_parameter(param)
        authenticate = None
        if self.authenticate is not None:
            authenticate = _compile_authenticate(
                self.authenticate,
                context,
                param,
                self._challenge("invalid_token"),
                credential_type=str,
                scheme="Bearer",
            )

        async def resolve(context: InvocationContext) -> object:
            connection = await context.resolve(HTTPConnection)
            if connection.scope["type"] != "http":
                raise InvalidDependencyError("Bearer credentials can only be resolved for HTTP requests.")

            if self in context.cache:
                return context.cache[self]

            values = connection.headers.getlist("authorization")
            if not values:
                raise NotAuthenticatedError(
                    "Bearer credentials are required.",
                    headers={"WWW-Authenticate": self._challenge()},
                )

            if len(values) != 1:
                raise BadRequestError(
                    "Malformed Bearer credentials.",
                    headers={"WWW-Authenticate": self._challenge("invalid_request")},
                )

            value = values[0].strip(" \t")
            scheme, token = _split_authorization(value)
            if scheme and scheme != "bearer":
                raise NotAuthenticatedError(
                    "Bearer credentials are required.",
                    headers={"WWW-Authenticate": self._challenge()},
                )

            token_body = token.rstrip("=")
            if token_body and all(char in _BEARER_TOKEN_CHARACTERS for char in token_body):
                resolved = token if authenticate is None else await authenticate(token, context)
                context.cache[self] = resolved
                return resolved

            raise BadRequestError(
                "Malformed Bearer credentials.",
                headers={"WWW-Authenticate": self._challenge("invalid_request")},
            )

        return resolve

    def to_openapi(self, param: ParamInfo, _context: openapi.SchemaContext) -> openapi.Contribution:
        self._validate_parameter(param)
        return openapi.Contribution(
            security_schemes={
                self.name: openapi.SecurityScheme(
                    type=openapi.SecuritySchemeType.HTTP,
                    scheme="bearer",
                    bearer_format=self.bearer_format,
                )
            },
            security={self.name: ()},
        )


@dataclasses.dataclass(frozen=True, slots=True, eq=False)
class OAuth2[T = typing.Never]:
    """Authenticate an OAuth2 Bearer token and enforce its required scopes."""

    realm: str
    flows: openapi.OAuthFlows
    name: str = "oauth2"
    required_scopes: tuple[str, ...] = ()
    authenticate: typing.Callable[..., Identity[T] | typing.Awaitable[Identity[T]]] | None = None
    _bearer: Bearer[T] = dataclasses.field(init=False, repr=False)

    def __post_init__(self) -> None:
        scopes = tuple(dict.fromkeys(self.required_scopes))
        if any(_OAUTH_SCOPE.fullmatch(scope) is None for scope in scopes):
            raise ValueError("OAuth2 required scopes must be non-empty printable ASCII strings without spaces.")

        if scopes and self.authenticate is None:
            raise ValueError("OAuth2 required_scopes requires authenticate.")

        object.__setattr__(self, "required_scopes", scopes)
        object.__setattr__(
            self,
            "_bearer",
            Bearer(realm=self.realm, name=self.name, authenticate=self.authenticate),
        )

    def dependency_info(self) -> CallableInfo[..., typing.Any] | None:
        return self._bearer.dependency_info()

    def compile(self, context: CompileContext, param: ParamInfo) -> Resolver:
        resolve_bearer = self._bearer.compile(context, param)

        async def resolve(invocation: InvocationContext) -> object:
            resolved = await resolve_bearer(invocation)
            if not self.required_scopes:
                return resolved

            identity = typing.cast(Identity[T], resolved)
            if identity.scopes.issuperset(self.required_scopes):
                return identity

            scope = " ".join(self.required_scopes)
            raise NotAuthorizedError(
                "OAuth2 identity does not grant the required scopes.",
                headers={
                    "WWW-Authenticate": self._bearer._challenge("insufficient_scope", scope),
                },
            )

        return resolve

    def to_openapi(self, param: ParamInfo, _context: openapi.SchemaContext) -> openapi.Contribution:
        self._bearer._validate_parameter(param)
        return openapi.Contribution(
            security_schemes={
                self.name: openapi.SecurityScheme(
                    type=openapi.SecuritySchemeType.OAUTH2,
                    flows=self.flows,
                )
            },
            security={self.name: self.required_scopes},
        )
