import typing as t

from kupala.contracts import TemplateRenderer


class FormatRenderer(TemplateRenderer):
    def render(self, template_name: str, context: t.Dict = None) -> str:
        return template_name % (context or {})
