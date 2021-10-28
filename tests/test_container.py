import pytest

from kupala.container import BaseAbstractFactory, Container, Key, Resolver, Scope, ServiceNotFoundError


class ExampleService:
    pass


@pytest.fixture
def container() -> Container:
    return Container()


def test_bind(container: Container) -> None:
    """Container.bind must set instance to the container and return the same instance back."""
    instance = ExampleService()
    container.bind(ExampleService, instance)
    assert container.resolve(ExampleService) == instance
    assert instance == container.resolve(ExampleService)


@pytest.mark.parametrize("scope", [Scope.TRANSIENT, Scope.SINGLETON])
def test_factory(container: Container, scope: Scope) -> None:
    """Container.register must call a factory function to create a instance.

    * if scope is Scope.TRANSIENT then a new instance to be created on each call.
    * if scope is Scope.SINGLETON then an instance gets created once and cached returning
    the same object on any subsequent call.
    """

    def factory(resolver: Resolver) -> ExampleService:
        return ExampleService()

    container.factory(ExampleService, factory, scope=scope)
    instance = container.resolve(ExampleService)
    assert isinstance(instance, ExampleService)

    if scope == Scope.SINGLETON:
        assert instance == container.resolve(ExampleService)
    elif scope == Scope.TRANSIENT:
        assert instance != container.resolve(ExampleService)


@pytest.mark.parametrize("scope", [Scope.TRANSIENT, Scope.SINGLETON])
def test_factory_with_initializer(container: Container, scope: Scope) -> None:
    """Container.register must accept 'initializer' argument which is a callable object.
    The initializer must be called right after the service creation.

    If scope is Scope.SINGLETON then the initialize must be called only once."""

    class StubWithArgs:
        def __init__(self, a: str, b: str = None) -> None:
            self.a = a
            self.b = b

    def initializer(resolver: Resolver, instance: StubWithArgs) -> None:
        instance.b = "b"

    def factory(resolver: Resolver) -> StubWithArgs:
        return StubWithArgs('a')

    container.factory(StubWithArgs, factory, initializer=initializer, scope=scope)
    instance = container.resolve(StubWithArgs)
    assert instance.a == "a"
    assert instance.b == "b"

    if scope == Scope.SINGLETON:
        assert instance == container.resolve(StubWithArgs)


def test_resolves_uses_parent_container() -> None:
    """Container constructor must accept 'parent' argument which is the reference to another container.
    The Container.resolve must ask parent container for a service resolution
    if the service cannot be found in the current container."""
    parent = Container()
    parent.bind(int, 1)
    container = Container(parent=parent)
    assert container.resolve(int) == 1


def test_fails_when_service_not_registered() -> None:
    """Container.resolve must fail when resolving a service which is not registered in the container."""
    container = Container()
    with pytest.raises(ServiceNotFoundError):
        container.resolve(int)

    parent = Container()
    container = Container(parent=parent)

    with pytest.raises(ServiceNotFoundError):
        container.resolve(int)


class StubAbsFactory(BaseAbstractFactory):
    def can_create(self, key: Key) -> bool:
        return key == ExampleService

    def resolve(self, key: Key, resolver: Resolver) -> ExampleService:
        return ExampleService()


def test_use_abstract_factory(container: Container) -> None:
    container.add_abstract_factory(StubAbsFactory())
    assert isinstance(container.resolve(ExampleService), ExampleService)
