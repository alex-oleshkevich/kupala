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

    def make_injectable(self, klass: typing.Type[_T], factory: typing.Callable[[Kupala], _T]) -> None:
        """Make `klass` type injectable by adding `from_app` class method to the type."""
        make_app_injectable(klass, factory)

    def make_request_injectable(self, klass: typing.Type[_T], factory: typing.Callable[[Request], _T]) -> None:
        """Make `klass` type request injectable by adding `from_request` class method to the type."""
        make_request_injectable(klass, factory)

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


def injectable(factory: typing.Callable[[Kupala], _T]) -> typing.Callable[[typing.Type[_T]], typing.Type[_T]]:
    def wrapper(cls: typing.Type[_T]) -> typing.Type[_T]:
        setattr(cls, _FACTORY_ATTR, factory)
        return cls

    return wrapper


def request_injectable(factory: typing.Callable[[Request], _T]) -> typing.Callable[[typing.Type[_T]], typing.Type[_T]]:
    def wrapper(cls: typing.Type[_T]) -> typing.Type[_T]:
        setattr(cls, _REQUEST_FACTORY_ATTR, factory)
        return cls

    return wrapper


def make_request_injectable(klass: typing.Type[_T], factory: typing.Callable[[Request], _T]) -> None:
    """Convert regular class into a request injectable."""
    request_injectable(factory=factory)(klass)


def make_app_injectable(klass: typing.Type[_T], factory: typing.Callable[[Kupala], _T]) -> None:
    """Convert regular class into app injectable."""
    injectable(factory=factory)(klass)


def get_request_injection_factory(klass: typing.Type) -> typing.Callable[[typing.Any], typing.Any] | None:
    """Retrieve factory callable from `klass`. This factory can create new instances from request."""
    return getattr(klass, 'from_request', getattr(klass, _REQUEST_FACTORY_ATTR, None))


def get_app_injection_factory(klass: typing.Type) -> typing.Callable[[typing.Any], typing.Any] | None:
    """Retrieve factory callable from `klass`. This factory can create new instances from app instance."""
    return getattr(klass, 'from_app', getattr(klass, _FACTORY_ATTR, None))
