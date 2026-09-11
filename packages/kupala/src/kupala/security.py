import dataclasses
import re
import typing
from email.utils import quote

from starlette.requests import HTTPConnection

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
from kupala.errors import BadRequestError, InvalidCredentialsError, NotAuthenticatedError
from kupala.schema import openapi

__all__ = ["Bearer", "Identity"]

_BEARER_CREDENTIALS = re.compile(
    r"Bearer +(?P<token>[A-Za-z0-9._~+/-]+=*)",
    re.ASCII | re.IGNORECASE,
)
_COMPONENT_NAME = re.compile(r"[A-Za-z0-9._-]+", re.ASCII)


@dataclasses.dataclass(frozen=True, slots=True)
class Identity[T]:
    """An authenticated principal and the scopes granted to it."""

    principal: T
    scopes: frozenset[str] = dataclasses.field(default_factory=frozenset)


def _compile_authenticate[Credential, T](
    callback: typing.Callable[..., Identity[T] | typing.Awaitable[Identity[T]]],
    context: CompileContext,
    param: ParamInfo,
    challenge: str,
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

    def _challenge(self, error: str | None = None) -> str:
        values = [f'realm="{quote(self.realm)}"']
        if error is not None:
            values.append(f'error="{error}"')
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
            match = _BEARER_CREDENTIALS.fullmatch(value)
            if match is not None:
                token = match.group("token")
                resolved = token if authenticate is None else await authenticate(token, context)
                context.cache[self] = resolved
                return resolved

            scheme = value.split(maxsplit=1)[0].lower() if value else ""
            if scheme and scheme != "bearer":
                raise NotAuthenticatedError(
                    "Bearer credentials are required.",
                    headers={"WWW-Authenticate": self._challenge()},
                )

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
