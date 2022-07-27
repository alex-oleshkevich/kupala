from __future__ import annotations

import dataclasses

import typing

_T = typing.TypeVar('_T')


class InjectionError(Exception):
    pass


class InjectionAlreadyRegisteredError(InjectionError):
    pass


class InjectionNotFoundError(InjectionError):
    pass


class InjectableFactory(typing.Protocol):
    def __call__(self, registry: InjectionRegistry) -> typing.Any:
        ...


Scope = typing.Literal['global', 'request']


@dataclasses.dataclass
class Injectable:
    factory: InjectableFactory
    cached: bool = False
    instance: typing.Any = None
    scope: Scope = 'global'

    def resolve(self, registry: InjectionRegistry) -> typing.Any:
        if self.cached:
            if not self.instance:
                self.instance = self.factory(registry)
            return self.instance

        return self.factory(registry)


class InjectionRegistry:
    def __init__(self, injectables: dict[typing.Type[typing.Any], Injectable] | None = None) -> None:
        self._injectables: dict[typing.Any, Injectable] = injectables or {}

    def bind(self, type_name: typing.Type[_T], instance: _T) -> None:
        if type_name in self._injectables:
            raise InjectionAlreadyRegisteredError(
                f'Injection "{type_name.__class__.__name__}" has been already registered.'
            )
        self._injectables[type_name] = Injectable(factory=lambda x: None, cached=True, instance=instance)

    def register(
        self,
        type_name: typing.Type[_T],
        factory: InjectableFactory,
        cached: bool = False,
        scope: Scope = 'global',
    ) -> None:
        if type_name in self._injectables:
            raise InjectionAlreadyRegisteredError(
                f'Injection "{type_name.__class__.__name__}" has been already registered.'
            )
        self._injectables[type_name] = Injectable(factory=factory, cached=cached, scope=scope)

    def register_for_request(
        self,
        type_name: typing.Type[_T],
        factory: InjectableFactory,
        cached: bool = False,
    ) -> None:
        self.register(type_name, factory, cached, scope='request')

    def get(self, type_name: typing.Type[_T], scope: Scope = 'global') -> _T:
        if type_name not in self._injectables:
            raise InjectionNotFoundError(f'Dependency "{type_name.__class__.__name__}" is not registered.')

        injectable = self._injectables[type_name]
        if injectable.scope != scope:
            raise InjectionError(
                f'Dependency "{type_name.__class__.__name__}" is not registered for scope "global". '
                f'It is in "{injectable.scope}" scope.'
            )
        return self._injectables[type_name].resolve(self)

    def safe_get(self, type_name: typing.Type[_T]) -> _T | None:
        try:
            return self.get(type_name)
        except InjectionNotFoundError:
            return None

    def has(self, type_name: typing.Type[_T], scope: Scope = 'global') -> bool:
        injectable = self._injectables.get(type_name)
        return injectable is not None and injectable.scope == scope
