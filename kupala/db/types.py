import typing

from alembic.autogenerate.api import AutogenContext


class RendersMigrationType:
    """A helper for rendering propery SQLAlchemy types and imports in revision files."""

    def render_item(self, _type: typing.Any, _obj: typing.Any, autogen_context: AutogenContext) -> str:
        autogen_context.imports.add(self.get_import_name())
        return self.__class__.__name__

    def get_import_name(self) -> str:
        module_name = self.__class__.__module__
        class_name = self.__class__.__name__
        return f"from {module_name} import {class_name}"
