from unittest import mock

from alembic.autogenerate.api import AutogenContext

from kupala.db.types import RendersMigrationType


class _MyDbType(RendersMigrationType):
    pass


class TestRendersMigrationType:
    def test_render_item(self) -> None:
        mixin = _MyDbType()
        context = mock.MagicMock(spec=AutogenContext)
        class_name = mixin.render_item(None, None, context)
        assert class_name == "_MyDbType"
        context.imports.add.assert_called_once_with("from test_types import _MyDbType")
