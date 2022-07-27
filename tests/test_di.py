import pytest

from kupala.di import InjectionAlreadyRegisteredError, InjectionNotFoundError, InjectionRegistry


class InjectableOne:
    pass


class CachedInjectable:
    pass


class ScopedInjectable:
    pass


def make_injectable_one(registry: InjectionRegistry) -> InjectableOne:
    return InjectableOne()


def make_cached_injectable(registry: InjectionRegistry) -> CachedInjectable:
    return CachedInjectable()


def make_scoped_injectable(registry: InjectionRegistry) -> ScopedInjectable:
    return ScopedInjectable()


@pytest.fixture
def registry() -> InjectionRegistry:
    registry = InjectionRegistry()
    registry.register(InjectableOne, make_injectable_one)
    registry.register(CachedInjectable, make_cached_injectable, cached=True)
    registry.register_for_request(ScopedInjectable, make_scoped_injectable)

    return registry


def test_registry_resolves_dependency(registry: InjectionRegistry) -> None:
    instance = registry.get(InjectableOne)
    instance2 = registry.get(InjectableOne)
    assert isinstance(instance, InjectableOne)
    assert instance != instance2


def test_registry_resolves_cached_dependency(registry: InjectionRegistry) -> None:
    instance = registry.get(CachedInjectable)
    instance2 = registry.get(CachedInjectable)
    assert instance == instance2


def test_registry_resolves_scoped_dependency(registry: InjectionRegistry) -> None:
    instance = registry.get(ScopedInjectable, scope='request')
    assert instance is not None

    with pytest.raises(InjectionNotFoundError):
        registry.get(ScopedInjectable)  # attempt to get from global scope


def test_registry_raises_for_duplicate_binding() -> None:
    with pytest.raises(InjectionAlreadyRegisteredError):
        registry = InjectionRegistry()
        registry.register(InjectableOne, make_injectable_one)
        registry.register(InjectableOne, make_injectable_one)


def test_registry_raises_for_missing_binding() -> None:
    with pytest.raises(InjectionNotFoundError):
        registry = InjectionRegistry()
        registry.get(InjectableOne)


def test_registry_safe_get_should_not_raise() -> None:
    registry = InjectionRegistry()
    assert registry.safe_get(InjectableOne) is None


def test_injectable_decorator() -> None:
    registry = InjectionRegistry()

    @registry.injectable(InjectableOne)
    def make(_: InjectionRegistry) -> InjectableOne:
        return InjectableOne()

    assert registry.get(InjectableOne) is not None


class MultiDep:
    def __init__(self, dep1: InjectableOne, dep2: CachedInjectable) -> None:
        self.dep1 = dep1
        self.dep2 = dep2


def test_registry_resolve_injects_factory_dependencies() -> None:
    def make(dep1: InjectableOne, dep2: CachedInjectable) -> MultiDep:
        return MultiDep(dep1, dep2)

    registry = InjectionRegistry()
    registry.register(InjectableOne, make_injectable_one, cached=True)
    registry.register(CachedInjectable, make_cached_injectable, cached=True)
    registry.register(MultiDep, make, cached=True)

    instance = registry.get(MultiDep)
    assert instance is not None
    assert instance.dep1 == registry.get(InjectableOne)
    assert instance.dep2 == registry.get(CachedInjectable)


def test_registry_resolve_injects_factory_without_dependencies() -> None:
    def make() -> InjectableOne:
        return InjectableOne()

    registry = InjectionRegistry()
    registry.register(InjectableOne, make, cached=True)

    instance = registry.get(InjectableOne)
    assert instance is not None
