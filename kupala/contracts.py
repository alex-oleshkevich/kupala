import typing


class PasswordHasher(typing.Protocol):  # pragma: no cover
    def hash(self, plain_password: str) -> str:
        ...

    def verify(self, plain: str, hashed: str) -> bool:
        ...


class TemplateRenderer(typing.Protocol):  # pragma: nocover
    """Render template to string."""

    def render(self, template_name: str, context: typing.Dict = None) -> str:
        ...
