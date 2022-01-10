import typing


class FormatRenderer:
    def render(self, template_name: str, context: typing.Mapping = None) -> str:
        return template_name % (context or {})
