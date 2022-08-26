from kupala.application import App


def dummy_extension(app: App) -> None:
    app.state.register_called = True


def test_extensions() -> None:
    app = App("tests", secret_key="key", extensions=[dummy_extension])
    assert app.state.register_called
