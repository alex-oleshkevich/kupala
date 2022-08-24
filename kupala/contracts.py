import abc
import typing


class TemplateRenderer(abc.ABC):  # pragma: nocover
    """Render template to string."""

    @abc.abstractmethod
    def render(self, template_name: str, context: typing.Mapping[str, typing.Any] | None = None) -> str:
        ...
