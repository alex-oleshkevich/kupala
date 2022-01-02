import typing as t


class FormatRenderer:
    def render(self, template_name: str, context: t.Dict = None) -> str:
        return template_name % (context or {})
