import abc
import enum
import typing as t


class ContainerError(Exception):
    """Base class for service container exceptions."""


class ServiceNotFoundError(ContainerError):
    """Raised when service is not registered."""


S = t.TypeVar('S')
Key = t.Union[str, t.Type[S]]


class Resolver(t.Protocol):
    @t.overload
    def resolve(self, key: t.Type[S]) -> S:
        ...

    @t.overload
    def resolve(self, key: str) -> t.Any:
        ...

    def resolve(self, key: Key) -> t.Any:
        ...


Factory = t.Union[t.Callable[[Resolver], t.Any], type]
Initializer = t.Callable[[Resolver, t.Any], None]


class AbstractFactory(t.Protocol):
    def can_create(self, key: Key) -> bool:
        ...

    def resolve(self, key: Key, resolver: Resolver) -> t.Any:
        ...


class BaseAbstractFactory(abc.ABC):  # pragma: no cover
    def can_create(self, key: Key) -> bool:
        raise NotImplementedError()

    def resolve(self, key: Key, resolver: Resolver) -> t.Any:
        raise NotImplementedError()


class Scope(enum.Enum):
    TRANSIENT = 'transient'
    SINGLETON = 'singleton'
    SCOPED = 'scoped'


class ServiceResolver(abc.ABC):  # pragma: no cover
    def resolve(self) -> t.Any:
        raise NotImplementedError()


class InstanceResolver(ServiceResolver):
    def __init__(self, instance: t.Any) -> None:
        self.instance = instance

    def resolve(self) -> t.Any:
        return self.instance


class FactoryResolver(ServiceResolver):
    def __init__(
        self,
        resolver: Resolver,
        factory: Factory,
        initializer: Initializer = None,
    ) -> None:
        self.resolver = resolver
        self.factory = factory
        self.initializer = initializer

    def resolve(self) -> t.Any:
        instance = self.factory(self.resolver)

        if self.initializer:
            self.initializer(self.resolver, instance)
        return instance


class SingletonResolver(FactoryResolver):
    def __init__(self, *args: t.Any, **kwargs: t.Any) -> None:
        super().__init__(*args, **kwargs)
        self.instance = None

    def resolve(self) -> t.Any:
        if not self.instance:
            self.instance = super().resolve()
        return self.instance


class Container:
    def __init__(self, parent: Resolver = None) -> None:
        self._parent = parent
        self._instances: dict[Key, t.Any] = {}
        self._registry: dict[Key, ServiceResolver] = {}
        self._abs_factories: list[AbstractFactory] = []
        self._abs_factory_cache: dict[Key, AbstractFactory] = {}

    def bind(self, key: Key, instance: t.Any) -> None:
        """Add an instance to the container."""
        self._registry[key] = InstanceResolver(instance)

    def factory(
        self,
        key: Key,
        factory: Factory,
        scope: Scope = Scope.TRANSIENT,
        initializer: Initializer = None,
    ) -> None:
        if scope == Scope.SINGLETON:
            self._registry[key] = SingletonResolver(self, factory, initializer)
        else:
            self._registry[key] = FactoryResolver(self, factory, initializer)

    @t.overload
    def resolve(self, key: t.Type[S]) -> S:  # noqa
        ...

    @t.overload
    def resolve(self, key: str) -> t.Any:  # noqa
        ...

    def resolve(self, key: Key) -> t.Any:
        """Get a service instance from the container."""
        service_resolver = self._registry.get(key)
        if service_resolver is None:
            if self._parent is not None:
                return self._parent.resolve(key)

            abs_factory = self._get_abstract_factory_for(key)
            if abs_factory is None:
                raise ServiceNotFoundError('Service "%s" is not registered.' % key)
            return abs_factory.resolve(key, self)
        return service_resolver.resolve()

    def add_abstract_factory(self, factory: AbstractFactory) -> None:
        self._abs_factories.append(factory)

    def _get_abstract_factory_for(self, key: Key) -> t.Optional[AbstractFactory]:
        if key not in self._abs_factory_cache:
            for factory in self._abs_factories:
                if factory.can_create(key):
                    self._abs_factory_cache[key] = factory
                    break
        return self._abs_factory_cache.get(key)
