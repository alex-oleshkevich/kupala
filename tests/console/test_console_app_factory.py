from starlette.applications import Starlette

from kupala.console import Group, create_console_app


def test_create_console_app() -> None:
    app = create_console_app(Starlette())
    assert isinstance(app, Group)
