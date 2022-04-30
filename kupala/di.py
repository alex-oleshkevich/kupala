from __future__ import annotations

import abc
import inspect
import typing

if typing.TYPE_CHECKING:  # pragma: nocover
    from kupala.application import App
    from kupala.http.requests import Request

_T = typing.TypeVar('_T')
_FACTORY_ATTR = '__di_factory__'
_REQUEST_FACTORY_ATTR = '__di_request_factory__'


class InjectionError(Exception):
    pass


class Injector:
    def __init__(self, app: App) -> None:
        self.app = app
        self.preferences: dict[typing.Any, typing.Any] = {}

    def prefer_for(
        self, klass: typing.Any, factory_or_instance: typing.Any | typing.Callable[[App], typing.Any]
    ) -> None:
        """
        When some types (like protocols) cannot implement `from_app` or
        `from_request` methods, use this method to forcibly associate type with
        a value or factory function.

        When `factory_or_instance` is a variable then it will be returned in
        request of `make()` call. When `factory_or_instance` is callable(app)
        then it will be called each time the service is requested.
        """
        self.preferences[klass] = factory_or_instance

    def make_injectable(
        self,
        klass: typing.Type[_T],
        *,
        from_app_factory: typing.Callable[[App], _T] = None,
        from_request_factory: typing.Callable[[Request], _T] = None,
    ) -> None:
        """Make `klass` type injectable by adding `from_app` class method to the
        type."""
        make_injectable(klass, from_app_factory=from_app_factory, from_request_factory=from_request_factory)

    def make(self, klass: typing.Type[_T]) -> _T:
        """
        Find or create and instance for a given type.

        It will look up `from_app` class method on `klass` and call it if found.
        If `from_app` is not implemented then it will look up preferences, and
        it will raise `InjectionError` if nothing helped.
        """
        if callback := get_app_injection_factory(klass):
            return callback(self.app)

        if klass in self.preferences:
            if callable(self.preferences[klass]):
                return self.preferences[klass](self.app)
            return self.preferences[klass]

        raise InjectionError(f'Factory for type "{klass.__name__}" cannot be found in DI configuration.')


def injectable(
    *,
    from_app_factory: typing.Callable[[App], _T] = None,
    from_request_factory: typing.Callable[[Request], _T] = None,
) -> typing.Callable[[typing.Type[_T]], typing.Type[_T]]:
    assert from_app_factory or from_request_factory, 'Either "from_app_factory" or "from_request_factory" must be set.'

    def wrapper(cls: typing.Type[_T]) -> typing.Type[_T]:
        if from_app_factory:
            setattr(cls, _FACTORY_ATTR, from_app_factory)
        if from_request_factory:
            setattr(cls, _REQUEST_FACTORY_ATTR, from_request_factory)
        return cls

    return wrapper


def make_injectable(
    klass: typing.Type[_T],
    *,
    from_app_factory: typing.Callable[[App], _T] = None,
    from_request_factory: typing.Callable[[Request], _T] = None,
) -> None:
    """Convert regular class into app injectable."""
    injectable(from_app_factory=from_app_factory, from_request_factory=from_request_factory)(klass)


def get_request_injection_factory(klass: typing.Type) -> typing.Callable[[typing.Any], typing.Any] | None:
    """
    Retrieve factory callable from `klass`.

    This factory can create new instances from request.
    """
    return getattr(klass, 'from_request', getattr(klass, _REQUEST_FACTORY_ATTR, None))


def get_app_injection_factory(klass: typing.Type) -> typing.Callable[[typing.Any], typing.Any] | None:
    """
    Retrieve factory callable from `klass`.

    This factory can create new instances from app instance.
    """
    return getattr(klass, 'from_app', getattr(klass, _FACTORY_ATTR, None))


_SERVICE = typing.TypeVar('_SERVICE', covariant=True)


class ServiceFactory(typing.Protocol[_SERVICE]):
    def __call__(self, registry: InjectionRegistry) -> _SERVICE:
        ...


class Binding(abc.ABC):
    def resolve(self, registry: InjectionRegistry) -> typing.Any:
        raise NotImplementedError()


class FactoryBinding(Binding):
    def __init__(self, factory: ServiceFactory, cache: bool = False) -> None:
        self._factory = factory
        self._cache = cache
        self._cached_instance = None
        self._is_generator = inspect.isgeneratorfunction(factory)
        self._is_async_generator = inspect.isasyncgenfunction(factory)

    def resolve(self, registry: InjectionRegistry) -> typing.Any:
        if self._cache:
            if not self._cached_instance:
                self._cached_instance = self._instantiate(registry)
            return self._cached_instance

        return self._instantiate(registry)

    def _instantiate(self, registry: InjectionRegistry) -> typing.Any:
        return self._factory(registry)


class InstanceBinding(Binding):
    def __init__(self, instance: typing.Any) -> None:
        self.instance = instance

    def resolve(self, registry: InjectionRegistry) -> typing.Any:
        return self.instance


class InjectionPlan:
    def __init__(
        self, registry: InjectionRegistry, fn: typing.Callable, bindings: dict[typing.Hashable, Binding]
    ) -> None:
        self._registry = registry
        self._injections = bindings
        self._fn = fn


class InjectionRegistry:
    def __init__(self, bindings: typing.Mapping[typing.Any, Binding] | None = None) -> None:
        self._bindings = dict(bindings or {})

    def add_instance(self, key: typing.Hashable, instance: typing.Any) -> None:
        self._bindings[key] = InstanceBinding(instance)

    def add_factory(self, key: typing.Hashable, factory: ServiceFactory, cache: bool = False) -> None:
        self._bindings[key] = FactoryBinding(factory, cache)

    @typing.overload
    def resolve(self, service: typing.Type[_SERVICE]) -> _SERVICE:
        ...

    @typing.overload
    def resolve(self, service: typing.Any) -> typing.Any:
        ...

    def resolve(self, service: typing.Any) -> typing.Any:
        binding = self._bindings[service]
        return binding.resolve(self)

    def create_injection_plan(self, fn: typing.Callable) -> InjectionPlan:
        bindings: dict[typing.Hashable, Binding] = {}
        args = typing.get_type_hints(fn)
        for arg_name, arg_type in args.items():
            bindings[arg_name] = self._bindings[arg_type]
        return InjectionPlan(self, fn, bindings)
