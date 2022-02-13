import typing

from kupala.requests import Request

SERVICE = typing.TypeVar('SERVICE')


class PasswordHasher(typing.Protocol):  # pragma: no cover
    def hash(self, plain_password: str) -> str:
        ...

    def verify(self, plain: str, hashed: str) -> bool:
        ...


class TemplateRenderer(typing.Protocol):  # pragma: nocover
    """Render template to string."""

    def render(self, template_name: str, context: typing.Dict = None) -> str:
        ...


class ContextProcessor(typing.Protocol):  # pragma: nocover
    def __call__(self, request: Request) -> typing.Mapping:
        ...


class HasPreferredLanguage(typing.Protocol):  # pragma: nocover
    """Defines an object that can provide preselected language information."""

    def get_preferred_language(self) -> str | None:
        ...


class Translator:  # pragma: nocover
    def gettext(self, msg: str, **variables: typing.Any) -> str:
        ...

    def ngettext(self, /, singular: str, plural: str, count: int, **variables: typing.Any) -> str:
        ...
