import abc
import typing


class PasswordHasher(abc.ABC):  # pragma: no cover
    @abc.abstractmethod
    def hash(self, plain_password: str) -> str:
        ...

    @abc.abstractmethod
    def verify(self, plain: str, hashed: str) -> bool:
        ...


class TemplateRenderer(abc.ABC):  # pragma: nocover
    """Render template to string."""

    @abc.abstractmethod
    def render(self, template_name: str, context: typing.Dict = None) -> str:
        ...
