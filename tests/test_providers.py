from kupala.application import Kupala
from kupala.container import Container
from kupala.providers import Provider


class ExampleProvider(Provider):
    def register(self, container: Container) -> None:
        container['key'] = 'value'

    def bootstrap(self, container: Container) -> None:
        container['key2'] = 'value'


def test_applies_providers() -> None:
    app = Kupala(providers=[ExampleProvider()])
    app.bootstrap()
    assert 'key' in app.services
    assert 'key2' in app.services
