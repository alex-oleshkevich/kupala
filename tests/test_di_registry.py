from kupala.di import InjectionRegistry


class DepOne:
    pass


def test_registry_resolves_instance() -> None:
    instance = DepOne()
    registry = InjectionRegistry()
    registry.add_instance(DepOne, instance)

    assert registry.resolve(DepOne) == instance


def test_registry_creates_instance_via_factory() -> None:
    registry = InjectionRegistry()

    def factory(registry: InjectionRegistry) -> DepOne:
        return DepOne()

    registry.add_factory(DepOne, factory)

    first_instance = registry.resolve(DepOne)
    second_instance = registry.resolve(DepOne)
    assert first_instance != second_instance


def test_registry_returns_same_instance_via_cached_factory() -> None:
    registry = InjectionRegistry()

    def factory(registry: InjectionRegistry) -> DepOne:
        return DepOne()

    registry.add_factory(DepOne, factory, cache=True)

    first_instance = registry.resolve(DepOne)
    second_instance = registry.resolve(DepOne)
    assert first_instance == second_instance
