from kupala.application import App, Extension


class DummyExtension(Extension):
    def register(self, app: App) -> None:
        app.state.register_called = True

    def bootstrap(self, app: App) -> None:
        app.state.bootstrap_called = True


def test_extensions() -> None:
    app = App(secret_key="key", extensions=[DummyExtension()])
    assert app.state.register_called
    assert app.state.bootstrap_called
