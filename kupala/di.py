from __future__ import annotations

import typing

from kupala.requests import Request

if typing.TYPE_CHECKING:  # pragma: nocover
    from kupala.application import Kupala

_T = typing.TypeVar('_T')
_FACTORY_ATTR = '__di_factory__'
_REQUEST_FACTORY_ATTR = '__di_request_factory__'


class InjectionError(Exception):
    pass


class Injector:
    def __init__(self, app: Kupala) -> None:
        self.app = app
        self.preferences: dict[typing.Any, typing.Any] = {}

    def prefer_for(
        self, klass: typing.Any, factory_or_instance: typing.Any | typing.Callable[[Kupala], typing.Any]
    ) -> None:
        """When some types (like protocols) cannot implement `from_app` or `from_request` methods,
        use this method to forcibly associate type with a value or factory function.

        When `factory_or_instance` is a variable then it will be returned in request of `make()` call.
        When `factory_or_instance` is callable(app) then it will be called each time the service is requested."""
        self.preferences[klass] = factory_or_instance

    def make_injectable(
        self,
        klass: typing.Type[_T],
        *,
        from_app_factory: typing.Callable[[Kupala], _T] = None,
        from_request_factory: typing.Callable[[Request], _T] = None,
    ) -> None:
        """Make `klass` type injectable by adding `from_app` class method to the type."""
        make_injectable(klass, from_app_factory=from_app_factory, from_request_factory=from_request_factory)

    def make(self, klass: typing.Type[_T]) -> _T:
        """Find or create and instance for a given type.

        It will look up `from_app` class method on `klass` and call it if found.
        If `from_app` is not implemented then it will look up preferences,
        and it will raise `InjectionError` if nothing helped."""
        if callback := get_app_injection_factory(klass):
            return callback(self.app)

        if klass in self.preferences:
            if callable(self.preferences[klass]):
                return self.preferences[klass](self.app)
            return self.preferences[klass]

        raise InjectionError(f'Factory for type "{klass.__name__}" cannot be found in DI configuration.')


def injectable(
    *,
    from_app_factory: typing.Callable[[Kupala], _T] = None,
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
    from_app_factory: typing.Callable[[Kupala], _T] = None,
    from_request_factory: typing.Callable[[Request], _T] = None,
) -> None:
    """Convert regular class into app injectable."""
    injectable(from_app_factory=from_app_factory, from_request_factory=from_request_factory)(klass)


def get_request_injection_factory(klass: typing.Type) -> typing.Callable[[typing.Any], typing.Any] | None:
    """Retrieve factory callable from `klass`. This factory can create new instances from request."""
    return getattr(klass, 'from_request', getattr(klass, _REQUEST_FACTORY_ATTR, None))


def get_app_injection_factory(klass: typing.Type) -> typing.Callable[[typing.Any], typing.Any] | None:
    """Retrieve factory callable from `klass`. This factory can create new instances from app instance."""
    return getattr(klass, 'from_app', getattr(klass, _FACTORY_ATTR, None))
