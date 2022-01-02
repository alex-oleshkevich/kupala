import pytest

from kupala.container import BaseAbstractFactory, Container, ContainerError, Key, Resolver, Scope, ServiceNotFoundError


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

    def factory() -> ExampleService:
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

    def initializer(container: Container, instance: StubWithArgs) -> None:
        instance.b = "b"

    def factory() -> StubWithArgs:
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


def test_safe_resolve() -> None:
    """Container.safe_resolve returns None if service does not exists."""
    container = Container()
    assert container.safe_resolve(int) is None

    container.bind(int, 1)
    assert container.safe_resolve(int) == 1


def test_factory_injections(container: Container) -> None:
    class Injection:
        pass

    class Service:
        def __init__(self, injection: Injection) -> None:
            self.injection = injection

    injection = Injection()
    container.bind(Injection, injection)

    def factory(injection: Injection) -> Service:
        return Service(injection)

    container.factory(Service, factory)
    instance = container.resolve(Service)
    assert instance.injection == injection


class StubAbsFactory(BaseAbstractFactory):
    def can_create(self, key: Key) -> bool:
        return key == ExampleService

    def resolve(self, key: Key, resolver: Resolver) -> ExampleService:
        return ExampleService()


def test_use_abstract_factory(container: Container) -> None:
    container.add_abstract_factory(StubAbsFactory())
    assert isinstance(container.resolve(ExampleService), ExampleService)


def test_contains(container: Container) -> None:
    container.bind('key', 'value')
    assert 'key' in container
    assert 'other_key' not in container


def test_contains_in_parent(container: Container) -> None:
    container.bind('key', 'value')
    local_container = Container(parent=container)
    assert 'key' in local_container
    assert 'other_key' not in local_container


def test_setgetitem(container: Container) -> None:
    container['key'] = 'value'
    assert container['key'] == 'value'


def test_scoped_services(container: Container) -> None:
    class LonelyClass:
        ...

    container.factory(LonelyClass, lambda: LonelyClass(), scope=Scope.SCOPED)
    with container.change_context({}):
        instance1 = container.resolve(LonelyClass)
        instance2 = container.resolve(LonelyClass)
        assert instance1 == instance2

    with pytest.raises(ContainerError, match='Tried to instantiate a scoped service without an active context.'):
        container.resolve(LonelyClass)


def test_container_should_temporary_lease_context_to_parent() -> None:
    """When a child container resolves a scoped service bound in parent,
    the resolved service must be stored in the child container context, not in the parent."""
    parent_container = Container()
    parent_container.factory('someservice', lambda: ExampleService(), scope=Scope.SCOPED)

    container = Container(parent_container)
    with container.change_context({}):
        instance1 = container.resolve('someservice')
        instance2 = container.resolve('someservice')
        assert instance1 == instance2

    with pytest.raises(ContainerError, match='Tried to instantiate a scoped service without an active context.'):
        container.resolve('someservice')

    assert container._context.get() is None
    assert parent_container._context.get() is None


def test_aliased_service_bind(container: Container) -> None:
    container.bind('someservice', 'value', alias='aliased')
    assert container.resolve('someservice') == 'value'
    assert container.resolve('aliased') == 'value'


def test_aliased_service_factory(container: Container) -> None:
    container.add_factory('someservice', lambda: 'value', alias='aliased')
    assert container.resolve('someservice') == 'value'
    assert container.resolve('aliased') == 'value'


def test_aliased_service_singleton(container: Container) -> None:
    container.add_singleton('someservice', lambda: 'value', alias='aliased')
    assert container.resolve('someservice') == 'value'
    assert container.resolve('aliased') == 'value'


def test_aliased_service_scoped(container: Container) -> None:
    container.add_scoped('someservice', lambda: 'value', alias='aliased')
    with container.change_context({}):
        assert container.resolve('someservice') == 'value'
        assert container.resolve('aliased') == 'value'


def test_aliased_service_from_parent_container(container: Container) -> None:
    parent_container = Container()
    parent_container.bind('someservice', 'value')

    container = Container(parent=parent_container)
    container.alias('someservice', 'aliased')

    assert container.resolve('someservice') == 'value'
    assert container.resolve('aliased') == 'value'
