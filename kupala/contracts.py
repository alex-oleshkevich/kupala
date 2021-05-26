import abc
import typing as t

from kupala.requests import Request

Debug = bool


@t.runtime_checkable
class Identity(t.Protocol):  # pragma: no cover
    def get_identity(self) -> str:
        ...

    def get_id(self) -> t.Any:
        ...

    def get_hashed_password(self) -> str:
        ...


class IdentityProvider(abc.ABC):  # pragma: no cover
    async def find_by_identity(self, identity: str) -> t.Optional[Identity]:
        raise NotImplementedError()

    async def find_by_id(self, id: t.Any) -> t.Optional[Identity]:
        raise NotImplementedError()

    async def find_by_token(self, token: str) -> t.Optional[Identity]:
        raise NotImplementedError()


class TemplateRenderer(t.Protocol):  # pragma: no cover
    """A protocol that all renderer implementations must match."""

    def render(self, template: str, context: dict[str, t.Any] = None) -> str:
        ...


class URLResolver(abc.ABC):  # pragma: no cover
    """URL resolver specification."""

    @abc.abstractmethod
    def resolve(
        self,
        name: str,
        **path_params: dict,
    ) -> str:  # pragma: nocover
        raise NotImplementedError()


class Authenticator(t.Protocol):
    def __init__(self, user_provider: IdentityProvider, **kwargs: t.Any):
        ...

    async def authenticate(self, request: Request) -> t.Optional[Identity]:
        ...


class PasswordHasher(t.Protocol):
    def hash(self, plain: str) -> str:
        ...

    def verify(self, plain: str, hashed: str) -> bool:
        ...
