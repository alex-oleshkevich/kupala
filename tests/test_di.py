import pytest

from kupala.di import InjectionAlreadyRegisteredError, InjectionNotFoundError, InjectionRegistry


class InjectableOne:
    pass


class CachedInjectable:
    pass


def make_injectable_one(registry: InjectionRegistry) -> InjectableOne:
    return InjectableOne()


def make_cached_injectable(registry: InjectionRegistry) -> CachedInjectable:
    return CachedInjectable()


@pytest.fixture
def registry() -> InjectionRegistry:
    registry = InjectionRegistry()
    registry.register(InjectableOne, make_injectable_one)
    registry.register(CachedInjectable, make_cached_injectable, cached=True)

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
