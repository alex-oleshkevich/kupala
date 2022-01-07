from __future__ import annotations

import typing

from kupala.requests import Request

if typing.TYPE_CHECKING:  # pragma: nocover
    from kupala.application import Kupala

_T = typing.TypeVar('_T')


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

    def to_injectable(self, klass: typing.Type[_T], factory: typing.Callable[[Kupala], _T]) -> None:
        """Make `klass` type injectable by adding `from_app` class method to the type."""
        to_app_injectable(klass, factory)

    def to_request_injectable(self, klass: typing.Type[_T], factory: typing.Callable[[Request], _T]) -> None:
        """Make `klass` type request injectable by adding `from_request` class method to the type."""
        to_request_injectable(klass, factory)

    def make(self, klass: typing.Type[_T]) -> _T:
        """Find or create and instance for a given type.

        It will look up `from_app` class method on `klass` and call it if found.
        If `from_app` is not implemented then it will look up preferences,
        and it will raise `InjectionError` if nothing helped."""
        if callback := getattr(klass, 'from_app', None):
            return callback(self.app)

        if klass in self.preferences:
            if callable(self.preferences[klass]):
                return self.preferences[klass](self.app)
            return self.preferences[klass]

        raise InjectionError(f'Factory for type "{klass.__name__}" cannot be found in DI configuration.')


def to_request_injectable(klass: typing.Type[_T], factory: typing.Callable[[Request], _T]) -> None:
    """Convert regular class into a request injectable."""

    def augmentation(cls: typing.Type[_T], request: Request) -> _T:
        return factory(request)

    setattr(klass, 'from_request', classmethod(augmentation))


def to_app_injectable(klass: typing.Type[_T], factory: typing.Callable[[Kupala], _T]) -> None:
    """Convert regular class into app injectable."""

    def augmentation(cls: typing.Type[_T], app: Kupala) -> _T:
        return factory(app)

    setattr(klass, 'from_app', classmethod(augmentation))
