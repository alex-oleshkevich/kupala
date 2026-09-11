import dataclasses
import re

from starlette.requests import HTTPConnection

from kupala.dependencies import CompileContext, InvalidDependencyError, InvocationContext, ParamInfo, Resolver
from kupala.errors import BadRequestError, NotAuthenticatedError
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


@dataclasses.dataclass(frozen=True, slots=True, eq=False)
class Bearer:
    """Read an HTTP Bearer credential and describe the same OpenAPI security requirement."""

    name: str = "bearer"
    bearer_format: str | None = None
    realm: str | None = None

    def __post_init__(self) -> None:
        if _COMPONENT_NAME.fullmatch(self.name) is None:
            raise ValueError("Bearer name must contain only letters, digits, dots, hyphens, and underscores.")
        if self.realm is not None and not all(char.isascii() and char.isprintable() for char in self.realm):
            raise ValueError("Bearer realm must contain only printable ASCII characters.")

    def _validate_parameter(self, param: ParamInfo) -> None:
        if param.type is not str or param.optional:
            raise InvalidDependencyError(f"Bearer parameter {param.name!r} must be a required str.")

    def _challenge(self, error: str | None = None) -> str:
        values: list[str] = []
        if self.realm is not None:
            realm = self.realm.replace("\\", "\\\\").replace('"', '\\"')
            values.append(f'realm="{realm}"')
        if error is not None:
            values.append(f'error="{error}"')
        return "Bearer" if not values else f"Bearer {', '.join(values)}"

    def compile(self, _context: CompileContext, param: ParamInfo) -> Resolver:
        self._validate_parameter(param)

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
                context.cache[self] = token
                return token

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
