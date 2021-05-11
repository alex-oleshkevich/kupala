import abc
import typing as t


class Identity(t.Protocol):  # pragma: no cover
    def get_identity(self) -> str:
        ...

    def get_id(self) -> t.Any:
        ...

    def get_hashed_password(self) -> str:
        ...


class IdentityProvider(abc.ABC):  # pragma: no cover
    async def find_by_identity(self, identity: str) -> Identity:
        raise NotImplementedError()

    async def find_by_id(self, id: t.Any) -> Identity:
        raise NotImplementedError()

    async def find_by_token(self, token: str) -> Identity:
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
