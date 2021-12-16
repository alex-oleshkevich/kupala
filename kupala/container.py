from __future__ import annotations

from dataclasses import dataclass

import abc
import contextvars
import enum
import inspect
import typing as t
import uuid
from contextlib import contextmanager


class ContainerError(Exception):
    """Base class for service container exceptions."""


class ServiceNotFoundError(ContainerError):
    """Raised when service is not registered."""


class InjectionErrorType(enum.Enum):
    POSITIONAL_ONLY_ERROR = 'positional_argument'
    NOT_ANNOTATED_ERROR = 'not_annotated_argument'
    SERVICE_NOT_FOUND = 'service_not_found'


class InjectionError(ContainerError):
    """Raise if injection cannot be proceed."""

    ErrorType = InjectionErrorType

    def __init__(
        self, message: str, error_type: InjectionErrorType, invokation_target: t.Union[t.Callable, t.Type]
    ) -> None:
        class_name = invokation_target.__name__ if inspect.isclass(invokation_target) else invokation_target.__name__
        module_name = invokation_target.__module__
        addon = f'Tried to invoke: {module_name}.{class_name}{inspect.signature(invokation_target)}.'
        super().__init__(message + f'\n{addon}')
        self.error_type = error_type


S = t.TypeVar('S')
Key = t.Union[str, t.Type[S]]


class Resolver(t.Protocol):  # pragma: nocover
    @t.overload
    def resolve(self, key: t.Type[S]) -> S:
        ...

    @t.overload
    def resolve(self, key: str) -> t.Any:
        ...

    def resolve(self, key: Key) -> t.Any:
        ...

    def __contains__(self, item: Key) -> bool:
        ...


Factory = t.Union[t.Callable[[Resolver], t.Any], type]
Initializer = t.Callable[[Resolver, t.Any], None]


class AbstractFactory(t.Protocol):  # pragma: nocover
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
    def resolve(self, context: t.Optional[dict] = None) -> t.Any:
        raise NotImplementedError()


class InstanceResolver(ServiceResolver):
    def __init__(self, instance: t.Any) -> None:
        self.instance = instance

    def resolve(self, context: t.Optional[dict] = None) -> t.Any:
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

    def resolve(self, context: t.Optional[dict] = None) -> t.Any:
        instance = self.factory(self.resolver)

        if self.initializer:
            self.initializer(self.resolver, instance)
        return instance


class SingletonResolver(FactoryResolver):
    def __init__(self, *args: t.Any, **kwargs: t.Any) -> None:
        super().__init__(*args, **kwargs)
        self.instance = None

    def resolve(self, context: t.Optional[dict] = None) -> t.Any:
        if not self.instance:
            self.instance = super().resolve(context)
        return self.instance


class ScopedResolver(FactoryResolver):
    def __init__(self, *args: t.Any, **kwargs: t.Any) -> None:
        super().__init__(*args, **kwargs)
        self._resolver_id = uuid.uuid4()

    def resolve(self, context: t.Optional[dict] = None) -> t.Any:
        if context is None:
            raise ContainerError('Tried to instantiate a scoped service without an active context.')

        if self._resolver_id not in context:
            context[self._resolver_id] = super().resolve(context)
        return context[self._resolver_id]


class Container:
    def __init__(self, parent: Container = None) -> None:
        self._parent = parent
        self._instances: dict[Key, t.Any] = {}
        self._registry: dict[Key, ServiceResolver] = {}
        self._abs_factories: list[AbstractFactory] = []
        self._abs_factory_cache: dict[Key, AbstractFactory] = {}
        self._context: contextvars.ContextVar[t.Optional[dict]] = contextvars.ContextVar('_context', default=None)

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
        elif scope == Scope.SCOPED:
            self._registry[key] = ScopedResolver(self, factory, initializer)
        else:
            self._registry[key] = FactoryResolver(self, factory, initializer)

    def add_singleton(self, key: Key, factory: Factory, initializer: Initializer = None) -> None:
        return self.factory(key, factory, scope=Scope.SINGLETON, initializer=initializer)

    def add_scoped(self, key: Key, factory: Factory, initializer: Initializer = None) -> None:
        return self.factory(key, factory, scope=Scope.SCOPED, initializer=initializer)

    def resolve(self, key: t.Any) -> t.Any:
        """Get a service instance from the container.

        fixme: https://github.com/python/mypy/issues/4717
        """
        service_resolver = self._registry.get(key)

        if service_resolver is None:
            if self._parent is not None:
                with self._parent.change_context(self._context.get()):
                    return self._parent.resolve(key)

            abs_factory = self._get_abstract_factory_for(key)
            if abs_factory is None:
                raise ServiceNotFoundError('Service "%s" is not registered.' % key)
            return abs_factory.resolve(key, self)

        return service_resolver.resolve(self._context.get())

    def safe_resolve(self, key: t.Any) -> t.Optional[t.Any]:
        """Return None if service does not exist instead of raising ServiceNotFoundError."""
        try:
            return self.resolve(key)
        except ServiceNotFoundError:
            return None

    def invoke(self, fn_or_class: t.Union[t.Callable, t.Type], extra_kwargs: t.Dict[str, t.Any] = None) -> t.Any:
        """Invoke a callable resolving and injecting dependencies."""
        injections = {}
        extra_kwargs = extra_kwargs or {}

        for argument in get_callable_types(fn_or_class):
            if argument.name in extra_kwargs:
                injections[argument.name] = extra_kwargs[argument.name]
                continue

            if argument.is_positional_only:
                raise InjectionError(
                    'Position-only arguments are not supported. ', InjectionErrorType.POSITIONAL_ONLY_ERROR, fn_or_class
                )
            if not argument.is_annotated:
                raise InjectionError(
                    f'Argument "{argument.name}" is not annotated thus injector cannot resolve object to inject. ',
                    InjectionErrorType.NOT_ANNOTATED_ERROR,
                    fn_or_class,
                )

            try:
                injections[argument.name] = self.resolve(argument.annotation)
            except ServiceNotFoundError as ex:
                raise InjectionError(
                    f'Argument "{argument.name}" refers to unregistered service "{argument.annotation}". ',
                    InjectionErrorType.SERVICE_NOT_FOUND,
                    fn_or_class,
                ) from ex

        if inspect.iscoroutinefunction(fn_or_class):

            async def wrapper() -> t.Any:
                return await fn_or_class(**injections)

            return wrapper()
        else:
            return fn_or_class(**injections)

    def add_abstract_factory(self, factory: AbstractFactory) -> None:
        self._abs_factories.append(factory)

    @contextmanager
    def change_context(self, context_data: t.Optional[dict] = None) -> t.Generator[Container, None, None]:
        try:
            self._context.set(context_data)
            yield self
        finally:
            self._context.set(None)

    def _get_abstract_factory_for(self, key: Key) -> t.Optional[AbstractFactory]:
        if key not in self._abs_factory_cache:
            for factory in self._abs_factories:
                if factory.can_create(key):
                    self._abs_factory_cache[key] = factory
                    break
        return self._abs_factory_cache.get(key)

    __setitem__ = bind
    __getitem__ = resolve

    def __contains__(self, item: Key) -> bool:
        has_in_self = item in self._registry
        has_in_parent = item in self._parent if self._parent else False
        return any([has_in_self, has_in_parent])


undefined = object()


@dataclass
class _Argument:
    name: str
    kind: int
    annotation: t.Type
    default: t.Any = undefined

    @property
    def has_default(self) -> bool:
        return self.default is not undefined

    @property
    def is_annotated(self) -> bool:
        return self.annotation is not undefined

    @property
    def is_positional_only(self) -> bool:
        return self.kind == inspect.Parameter.POSITIONAL_ONLY

    @property
    def is_keyword(self) -> bool:
        return self.kind in [inspect.Parameter.KEYWORD_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD]


@dataclass
class FunctionTypes:
    arguments: dict[str, _Argument]
    return_type: t.Type

    @property
    def is_return_type_annotated(self) -> bool:
        return self.return_type is not undefined

    def __iter__(self) -> t.Iterator[_Argument]:
        return iter(self.arguments.values())

    def __len__(self) -> int:
        return len(self.arguments)

    def __contains__(self, item: str) -> bool:
        return item in self.arguments

    def __getitem__(self, item: str) -> _Argument:
        return self.arguments[item]


def get_callable_types(fn: t.Union[t.Callable, t.Type]) -> FunctionTypes:
    for_checking = []
    is_class = inspect.isclass(fn)
    if is_class:
        for base in getattr(fn, "__mro__", []):
            if base != object:
                for_checking.append(getattr(base, "__init__"))
    else:
        for_checking.append(fn)

    arguments = {}

    def _get_annotation(param: inspect.Parameter, fn_to_check: t.Callable) -> t.Any:
        if param.annotation == inspect.Parameter.empty:
            return undefined

        type_hints = t.get_type_hints(fn_to_check)
        return type_hints[param.name]

    return_annotation: t.Any = undefined
    for fn_to_check in reversed(for_checking):
        signature = inspect.signature(fn_to_check)
        return_annotation = t.get_type_hints(fn_to_check).get('return', undefined)

        for name, param in signature.parameters.items():
            if param.kind in [inspect.Parameter.VAR_KEYWORD, inspect.Parameter.VAR_POSITIONAL]:
                # ignore *args, **kwargs
                continue
            arguments[name] = _Argument(
                name=name,
                kind=param.kind,
                annotation=_get_annotation(param, fn_to_check),
                default=undefined if param.default == signature.empty else param.default,
            )

    if is_class and 'self' in arguments:
        del arguments['self']

    return FunctionTypes(arguments, return_annotation)
