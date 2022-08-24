import typing

from kupala.contracts import TemplateRenderer


class FormatRenderer(TemplateRenderer):
    def render(self, template_name: str, context: typing.Mapping[str, typing.Any] = None) -> str:
        return template_name % (context or {})
