from dataclasses import dataclass

import typing as t

from kupala.middleware import Middleware


@dataclass
class ResourceAction:
    path: str
    methods: list[str]
    path_name: str
    scope: t.Literal['collection', 'object']
    include_in_schema: bool
    middleware: t.Sequence[Middleware]

    @property
    def is_for_object(self) -> bool:
        return self.scope == 'object'


def action(
    path: str,
    methods: list[str] = None,
    path_name: str = None,
    scope: t.Literal['object', 'collection'] = 'collection',
    include_in_schema: bool = True,
    middleware: t.Sequence[Middleware] = None,
) -> t.Callable:
    """Mark resource class method as custom action."""
    assert path.startswith("/"), "Routed paths must start with '/'"

    def wrapper(fn: t.Callable) -> t.Callable:
        setattr(
            fn,
            'action',
            ResourceAction(
                path=path,
                methods=methods or ['GET', 'HEAD'],
                path_name=path_name or fn.__name__,
                scope=scope,
                include_in_schema=include_in_schema,
                middleware=middleware or [],
            ),
        )
        return fn

    return wrapper


def get_resource_action(method: t.Callable) -> t.Optional[ResourceAction]:
    """Get resource action spec from resource method."""
    return getattr(method, 'action', None)
