from kupala.application import Kupala
from kupala.providers import Provider


class ExampleProvider(Provider):
    def register(self, app: Kupala) -> None:
        app.services['key'] = 'value'

    def bootstrap(self, app: Kupala) -> None:
        app.services['key2'] = 'value'


def test_applies_providers() -> None:
    app = Kupala(providers=[ExampleProvider()])
    app.bootstrap()
    assert 'key' in app.services
    assert 'key2' in app.services
