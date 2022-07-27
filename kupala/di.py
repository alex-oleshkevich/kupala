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


InjectableFactory = typing.Callable

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
                self.instance = self._do_resolve(registry)
            return self.instance

        return self._do_resolve(registry)

    def _do_resolve(self, registry: InjectionRegistry) -> typing.Any:
        args = typing.get_type_hints(self.factory)
        injections = {}
        for arg_name, arg_type in args.items():
            if arg_name == 'return':
                continue
            injections[arg_name] = registry.get(arg_type)
        return self.factory(**injections)


class InjectionRegistry:
    def __init__(self) -> None:
        self._scopes: dict[str, dict[typing.Any, Injectable]] = {
            'global': {},
            'request': {},
        }
        self._scopes['global'][self.__class__] = Injectable(factory=lambda x: None, cached=True, instance=self)

    def bind(self, type_name: typing.Type[_T], instance: _T, scope: Scope = 'global') -> None:
        self._ensure_not_exists(type_name, scope)
        self._scopes[scope][type_name] = Injectable(factory=lambda x: None, cached=True, instance=instance)

    def register(
        self,
        type_name: typing.Type[_T],
        factory: InjectableFactory,
        cached: bool = False,
        scope: Scope = 'global',
    ) -> None:
        self._ensure_not_exists(type_name, scope)
        self._scopes[scope][type_name] = Injectable(factory=factory, cached=cached)

    def register_for_request(
        self,
        type_name: typing.Type[_T],
        factory: InjectableFactory,
        cached: bool = False,
    ) -> None:
        self.register(type_name, factory, cached, scope='request')

    def get(self, type_name: typing.Type[_T], scope: Scope = 'global') -> _T:
        if type_name not in self._scopes[scope]:
            raise InjectionNotFoundError(f'Dependency "{type_name.__name__}" is not registered in scope "{scope}".')

        injectable = self._scopes[scope][type_name]
        return injectable.resolve(self)

    def safe_get(self, type_name: typing.Type[_T], scope: Scope = 'global') -> _T | None:
        try:
            return self.get(type_name, scope)
        except InjectionNotFoundError:
            return None

    def has(self, type_name: typing.Type[_T], scope: Scope = 'global') -> bool:
        return type_name in self._scopes[scope]

    def _ensure_not_exists(self, type_name: typing.Any, scope: Scope) -> None:
        if type_name in self._scopes[scope]:
            raise InjectionAlreadyRegisteredError(
                f'Injection "{type_name.__class__.__name__}" has been already registered in scope "{scope}".'
            )

    _PS = typing.ParamSpec('_PS')
    _RT = typing.TypeVar('_RT')

    def injectable(
        self,
        type_name: typing.Any,
        scope: Scope = 'global',
    ) -> typing.Callable[[InjectableFactory], InjectableFactory]:
        def wrapper(fn: InjectableFactory) -> InjectableFactory:
            self.register(type_name, fn, scope=scope)
            return fn

        return wrapper
