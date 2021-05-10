from __future__ import annotations

import inspect
import typing as t

S = t.TypeVar("S", bound=type)
N = t.Union[str, type]
Factory = t.Callable[[], t.Union[S, t.Any]]
PostCreateHook = t.Callable[[t.Union[S, t.Any]], None]


class ContainerError(Exception):
    """Base exception for all container errors."""


class AliasExistsError(ContainerError):
    """Raised when alias name is already taken."""


class ServiceNotFound(ContainerError):
    """Raised when container fails to retrieve service."""


class ParameterUnsupported(ContainerError):
    """Raised if function or constructor parameter cannot be processed."""


class PositionOnlyArgumentError(ParameterUnsupported):
    """Raised if function or constructor parameter is of positional type."""


class NoTypeHintError(ContainerError):
    """Raised if function or constructor parameter has no type hint."""


class Binding:
    def __init__(self, service: N, container: Container):
        self._service = service
        self._container = container

    def alias(self, aliases: t.Union[N, list[N]]) -> Binding:
        """Alias an existing services with an alternate name."""
        self._container.alias(self._service, aliases)
        return self

    def tag(self, tags: t.Union[str, list[str]]) -> Binding:
        """Assign tags to a service."""
        self._container.tag(self._service, tags)
        return self

    def after_created(self, hook: PostCreateHook) -> Binding:
        """Call a hook after the service has been created by factory."""
        self._container.add_post_create_hook(self._service, hook)
        return self


class FactorySpec:
    def __init__(self, factory: Factory, singleton: bool):
        self.factory = factory
        self.singleton = singleton


class _ServiceGetter:
    def __init__(self, name: str):
        self.name = name


def service(name: str) -> _ServiceGetter:
    """Inject a dependency using a string service name."""
    return _ServiceGetter(name)


class ByTag:
    def __init__(self, tag: str):
        self.tag = tag


def tag(tag: str) -> ByTag:
    """Inject a list of dependencies for a specific tag."""
    return ByTag(tag)


class Container:
    """A container for registered service instances and factories."""

    def __init__(self) -> None:
        self._instances: dict[N, t.Any] = {}
        self._factories: dict[N, FactorySpec] = {}
        self._aliases: dict[N, N] = {}
        self._tags: dict[str, list[N]] = {}
        self._post_create_hooks: dict[N, list[PostCreateHook]] = {}

    @property
    def aliases(self) -> dict[N, N]:
        return self._aliases

    @property
    def tags(self) -> dict[str, list[N]]:
        return self._tags

    def get(self, name: N) -> S:
        """Retrieve a service instance from the container."""
        real_name = self.resolve(name)
        if real_name not in self:
            raise ServiceNotFound('Service "%s" is not registered.' % name)

        if real_name in self._instances:
            return self._instances[real_name]

        factory = self._factories[real_name]
        instance = self.invoke(factory.factory)
        if factory.singleton:
            self._instances[name] = instance
        callbacks = self._post_create_hooks.get(name, [])
        for callback in callbacks:
            callback(instance)
        return instance

    def invoke(self, fn: t.Union[t.Callable, type], **args: t.Any) -> t.Any:
        """Invoke a callable or class constructor injecting dependencies."""
        signature = inspect.signature(fn)
        if inspect.isclass(fn):
            type_hints = t.get_type_hints(getattr(fn, "__init__"))
        else:
            type_hints = t.get_type_hints(fn)

        injections = args
        for p in signature.parameters.values():
            if p.kind == inspect.Parameter.POSITIONAL_ONLY:
                raise PositionOnlyArgumentError(
                    'Argument "%s" of "%s": '
                    "positional only arguments not supported. " % (p.name, fn)
                )

            if p.name not in injections:
                if p.name not in type_hints:
                    raise NoTypeHintError(
                        'Argument "%s" of "%s" has no type hint.' % (
                            p.name, fn
                        ))

                dependency_type = type_hints[p.name]
                resolved_dep: t.Any
                if isinstance(dependency_type, _ServiceGetter):
                    resolved_dep = self.get(dependency_type.name)
                elif isinstance(dependency_type, ByTag):
                    resolved_dep = self.get_by_tag(dependency_type.tag)
                else:
                    resolved_dep = self.get(dependency_type)
                injections[p.name] = resolved_dep

        return fn(**injections)

    def bind(
            self,
            name: N,
            instance: t.Any,
            aliases: t.Union[N, list[N]] = None,
            tags: t.Union[str, list[str]] = None,
    ) -> Binding:
        """Bind an instance to the container.
        A cached instance always returned."""
        self._instances[name] = instance
        if aliases:
            self.alias(name, aliases)
        if tags:
            self.tag(name, tags)
        return Binding(name, self)

    def factory(
            self,
            name: N,
            factory: Factory,
            singleton: bool = False,
            aliases: t.Union[N, list[N]] = None,
            tags: t.Union[str, list[str]] = None,
    ) -> Binding:
        """Bind a services factory.
        The service factory is a callable that creates a service instance.
        By default, it always creates a fresh instance unless `singleton`
        is specified."""
        self._factories[name] = FactorySpec(factory, singleton)
        if aliases:
            self.alias(name, aliases)
        if tags:
            self.tag(name, tags)
        return Binding(name, self)

    def singleton(
            self,
            name: t.Union[str, S],
            factory: Factory,
            aliases: t.Union[N, list[N]] = None,
            tags: t.Union[str, list[str]] = None,
    ) -> Binding:
        """Bind a factory for a singleton service.
        Each time you ask for a service, a cached instance will be returned."""
        return self.factory(
            name, factory, singleton=True, aliases=aliases, tags=tags,
        )

    def alias(self, service: N, aliases: t.Union[N, list[N]]) -> None:
        """Alias an existing services with an alternate name."""
        aliases = [aliases] if isinstance(aliases, (str, type)) else aliases
        for alias_ in aliases:
            if alias_ in self._aliases:
                raise AliasExistsError(
                    'Alias %s is taken by "%s" service.'
                    % (
                        alias_,
                        self._aliases[alias_],
                    )
                )

            real_name = self.resolve(service)
            self._aliases[alias_] = real_name

    def get_aliases(self, service: N) -> list[t.Union[str, type]]:
        """Get all aliases assigned to the service."""
        return [
            alias for alias, real_name in self._aliases.items() if
            real_name == service
        ]

    def tag(self, service: N, tags: t.Union[str, list[str]]) -> None:
        """Assign tags to the service."""
        tags = [tags] if isinstance(tags, str) else tags
        for tag in tags:
            self._tags.setdefault(tag, [])
            self._tags[tag].append(service)

    def get_by_tag(self, tag: str) -> list[t.Any]:
        """Get services tagged with `tag`."""
        return list(map(self.get, self._tags.get(tag, [])))

    def get_tags(self, service: N) -> list[str]:
        """Get all tags assigned to the service."""
        return [tag for tag, services in self._tags.items() if
                service in services]

    def has(self, name: N) -> bool:
        """Test if container contains service `name`."""
        try:
            real_name = self.resolve(name)
            return any(
                [
                    real_name in self._instances,
                    real_name in self._factories,
                ]
            )
        except ServiceNotFound:
            return False

    def add_post_create_hook(self, name: N, hook: PostCreateHook) -> None:
        """Add a callable to execute after successful service creation."""
        self._post_create_hooks.setdefault(name, [])
        self._post_create_hooks[name].append(hook)

    def resolve(self, name: N) -> N:
        """Resolve a service name or an alias into an actual service name."""
        if name in self._aliases:
            return self.resolve(self._aliases[name])

        if not any([name in self._instances, name in self._factories]):
            raise ServiceNotFound(
                'Name "%s" not found in the container.' % name)
        return name

    def remove(self, name: N) -> None:
        """Remove service from the container.
        This will also remove all aliases and tags."""
        if name in self._instances:
            del self._instances[name]

        if name in self._factories:
            del self._factories

        for tag in self.get_tags(name):
            self._tags[tag].remove(name)
            if len(self._tags[tag]) == 0:
                del self._tags[tag]

        for alias in self.get_aliases(name):
            del self._aliases[alias]

        if name in self._post_create_hooks:
            del self._post_create_hooks[name]

    __contains__ = has
    __getitem__ = get
    __setitem__ = bind
    __delitem__ = remove
