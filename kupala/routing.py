from __future__ import annotations

import functools
import inspect
import typing as t
from os import PathLike
from starlette import routing
from starlette.concurrency import run_in_threadpool
from starlette.routing import WebSocketRoute, compile_path, get_name, iscoroutinefunction_or_partial
from starlette.staticfiles import StaticFiles
from starlette.types import ASGIApp, Receive, Scope, Send

from kupala.disks.file_server import FileServer
from kupala.exceptions import MethodNotAllowed
from kupala.middleware import Middleware
from kupala.requests import Request
from kupala.resources import get_resource_action
from kupala.responses import RedirectResponse
from kupala.utils import camel_to_snake, import_string


def apply_middleware(app: t.Callable, middleware: t.Sequence[Middleware]) -> ASGIApp:
    for mw in reversed(middleware):
        app = mw.wrap(app)
    return app


def request_response(func: t.Callable) -> ASGIApp:
    """
    Takes a function or coroutine `func(request) -> response`,
    and returns an ASGI application.
    """
    is_coroutine = iscoroutinefunction_or_partial(func)

    # determine request class
    request_class = t.get_type_hints(func).get('request', Request)

    async def app(scope: Scope, receive: Receive, send: Send) -> None:
        request: Request = request_class(scope, receive, send)
        extra_kwargs = {'request': request, **request.path_params}

        if is_coroutine:
            response = await request.app.invoke(func, extra_kwargs=extra_kwargs)
        else:
            response = await run_in_threadpool(request.app.invoke, func, extra_kwargs=extra_kwargs)
        await response(scope, receive, send)

    return app


class Mount(routing.Mount):
    def __init__(
        self,
        path: str,
        app: ASGIApp = None,
        routes: t.Sequence[routing.BaseRoute] = None,
        name: str = None,
        *,
        middleware: t.Sequence[Middleware] = None,
    ) -> None:
        assert path == "" or path.startswith("/"), "Routed paths must start with '/'"
        assert app is not None or routes is not None, "Either 'app=...', or 'routes=' must be specified"
        self.path = path.rstrip("/")
        if app is not None:
            self.app: ASGIApp = app
            self._routes = getattr(app, 'routes', [])
        else:
            self.app = Router(routes=routes)
            self._routes = list(routes or [])
        self.name = name
        self.path_regex, self.path_format, self.param_convertors = compile_path(self.path + "/{path:path}")

        if middleware:
            self.app = apply_middleware(self.app, middleware)

    @property
    def routes(self) -> list[routing.BaseRoute]:
        return self._routes


class Host(routing.Host):
    def __init__(self, host: str, app: ASGIApp, name: str = None, *, middleware: t.Sequence[Middleware] = None) -> None:
        self.host = host
        self.app = app
        self.name = name
        self.host_regex, self.host_format, self.param_convertors = compile_path(host)
        self.middleware = middleware
        self._routes = getattr(app, 'routes', [])

        if middleware:
            self.app = apply_middleware(self.app, middleware)

    @property
    def routes(self) -> list[routing.BaseRoute]:
        return self._routes


class Router(routing.Router):
    pass


class Route(routing.Route):
    def __init__(
        self,
        path: str,
        endpoint: t.Callable,
        *,
        name: str = None,
        include_in_schema: bool = True,
        methods: list[str] = None,
        middleware: t.Sequence[Middleware] = None,
    ) -> None:
        assert path.startswith("/"), "Routed paths must start with '/'"
        self.path = path
        self.endpoint = endpoint
        self.name = get_name(endpoint) if name is None else name
        self.include_in_schema = include_in_schema

        endpoint_handler = endpoint
        while isinstance(endpoint_handler, functools.partial):
            endpoint_handler = endpoint_handler.func
        if inspect.isfunction(endpoint_handler) or inspect.ismethod(endpoint_handler):
            # Endpoint is function or method. Treat it as `func(request) -> response`.
            self.app = request_response(endpoint)
            if methods is None:
                methods = ["GET"]
        else:
            # Endpoint is a class. Treat it as ASGI.
            self.app = endpoint

        if middleware is not None:
            self.app = apply_middleware(t.cast(t.Callable, self.app), middleware)

        if methods is None:
            self.methods = None
        else:
            self.methods = {method.upper() for method in methods}
            if "GET" in self.methods:
                self.methods.add("HEAD")

        self.path_regex, self.path_format, self.param_convertors = compile_path(path)

    def __repr__(self) -> str:
        return f'<Route: path={self.path}, methods={self.methods}, name={self.name}>'


class _RouteAdapter:
    _routes: Routes
    _base_app: t.Optional[ASGIApp]

    def _create_base_asgi_app(self) -> ASGIApp:
        raise NotImplementedError()

    def __enter__(self) -> Routes:
        self._base_app = None  # force app recreate when routes change
        return self._routes

    def __exit__(self, *args: t.Any) -> None:
        pass

    def __getattr__(self, item: str) -> t.Any:
        try:
            return getattr(self._base_app, item)
        except AttributeError:
            self._base_app = self._create_base_asgi_app()
            return getattr(self._base_app, item)


class HostRoutes(_RouteAdapter):
    def __init__(
        self,
        host: str,
        routes: t.Union[list[routing.BaseRoute], Routes] = None,
        name: str = None,
        middleware: t.Sequence[Middleware] = None,
    ) -> None:
        self._host = host
        self._name = name
        self._routes = Routes(routes)
        self._middleware = middleware or []
        self._wrapped_app: t.Optional[ASGIApp] = None
        self._base_app: t.Optional[Host] = None

    def _create_base_asgi_app(self) -> ASGIApp:
        return Host(host=self._host, app=Router(routes=self._routes), name=self._name, middleware=self._middleware)


class GroupRoutes(_RouteAdapter):
    def __init__(
        self,
        prefix: str,
        routes: t.Union[list[routing.BaseRoute], Routes] = None,
        name: str = None,
        middleware: t.Sequence[Middleware] = None,
    ) -> None:
        self._name = name
        self._prefix = prefix
        self._routes = Routes(routes)
        self._middleware = middleware or []
        self._wrapped_app: t.Optional[ASGIApp] = None
        self._base_app: t.Optional[Mount] = None

    def _create_base_asgi_app(self) -> ASGIApp:
        return Mount(path=self._prefix, routes=self._routes, name=self._name, middleware=self._middleware)


class ResourceRoute(routing.BaseRoute):
    def __init__(
        self,
        path: str,
        resource: object,
        *,
        name: str = None,
        only: list[str] = None,
        exclude: list[str] = None,
        include_in_schema: bool = True,
        middleware: t.Sequence[Middleware] = None,
        redirect_slashes: bool = True,
        id_param: str = 'id:int',
    ) -> None:
        assert path == "" or path.startswith("/"), "Routed paths must start with '/'"
        assert bool(only and exclude) is False, '"exclude" and "only" arguments are mutually exclusive.'

        self.path = path.rstrip("/")
        self.name = name or camel_to_snake(resource.__class__.__name__).replace('_resource', '')
        self.only = only
        self.exclude = exclude
        self.resource = resource
        self.id_param = id_param
        self.middleware = middleware
        self.include_in_schema = include_in_schema

        self.collection_method_map: dict[str, t.Optional[t.Callable]] = {
            'head': getattr(self.resource, 'index', None),
            'get': getattr(self.resource, 'index', None),
            'post': getattr(self.resource, 'create', None),
        }
        self.object_method_map: dict[str, t.Optional[t.Callable]] = {
            'head': getattr(self.resource, 'show', None),
            'get': getattr(self.resource, 'show', None),
            'put': getattr(self.resource, 'update', None),
            'patch': getattr(self.resource, 'partial_update', getattr(self.resource, 'update', None)),
            'delete': getattr(self.resource, 'destroy', None),
        }

        routes = self._create_routes()
        self.app = Router(routes, redirect_slashes=redirect_slashes)

    def _create_routes(self) -> list[routing.BaseRoute]:
        return [
            *self._get_custom_action_routes(),
            *self._get_edit_routes(),
            *self._get_list_routes(),
            *self._get_object_routes(),
        ]

    @property
    def routes(self) -> list[routing.BaseRoute]:
        return getattr(self.app, "routes", [])

    def matches(self, scope: Scope) -> t.Tuple[routing.Match, Scope]:
        for route in self.routes:
            match, child_scope = route.matches(scope)
            if match != routing.Match.NONE:
                return match, child_scope
        return routing.Match.NONE, {}

    def url_path_for(self, name: str, **path_params: str) -> routing.URLPath:
        return self.app.url_path_for(name, **path_params)

    async def handle(self, scope: Scope, receive: Receive, send: Send) -> None:
        await self.app(scope, receive, send)

    def _get_list_routes(self) -> list[routing.BaseRoute]:
        routes: list[routing.BaseRoute] = []
        collection_route_methods: list[str] = []
        if self._is_action_allowed('index'):
            collection_route_methods.extend(['HEAD', 'GET'])
        if self._is_action_allowed('create'):
            collection_route_methods.append('POST')

        if collection_route_methods:
            routes.append(
                Route(
                    self.path,
                    self._list_view,
                    methods=collection_route_methods,
                    name=f'{self.name}.list',
                    include_in_schema=self.include_in_schema,
                    middleware=self.middleware,
                )
            )
        return routes

    def _get_object_routes(self) -> list[routing.BaseRoute]:
        routes: list[routing.BaseRoute] = []
        object_route_methods: list[str] = []
        if self._is_action_allowed('show'):
            object_route_methods.extend(['HEAD', 'GET'])
        if self._is_action_allowed('update'):
            object_route_methods.extend(['PUT', 'PATCH'])
        if self._is_action_allowed('destroy'):
            object_route_methods.append('DELETE')
        if object_route_methods:
            routes.append(
                Route(
                    '%s/{%s}' % (self.path, self.id_param),
                    self._object_view,
                    methods=object_route_methods,
                    name=f'{self.name}.detail',
                    include_in_schema=self.include_in_schema,
                    middleware=self.middleware,
                )
            )
        return routes

    def _get_edit_routes(self) -> list[routing.BaseRoute]:
        routes: list[routing.BaseRoute] = []
        new_action = getattr(self.resource, 'new', None)
        if self._is_action_allowed('new') and new_action:
            routes.append(Route('%s/new' % self.path, new_action, name=f'{self.name}.new', middleware=self.middleware))

        edit_action = getattr(self.resource, 'edit', None)
        if self._is_action_allowed('edit') and edit_action:
            routes.append(
                Route(
                    '%s/{%s}/edit' % (self.path, self.id_param),
                    edit_action,
                    name=f'{self.name}.edit',
                    middleware=self.middleware,
                )
            )
        return routes

    def _get_custom_action_routes(self) -> list[routing.BaseRoute]:
        routes: list[routing.BaseRoute] = []

        for name, fn in inspect.getmembers(self.resource, inspect.ismethod):
            action = get_resource_action(fn)
            if action and self._is_action_allowed(name):
                path = '{base}{id_param}{action}'.format(
                    base=self.path,
                    id_param=('/{%s}' % self.id_param if action.is_for_object else ''),
                    action=action.path,
                )
                routes.append(
                    Route(
                        path=path,
                        endpoint=fn,
                        name=f'{self.name}.{action.path_name}',
                        include_in_schema=action.include_in_schema,
                        methods=action.methods,
                        middleware=action.middleware,
                    )
                )

        return routes

    async def _list_view(self, request: Request) -> ASGIApp:
        action = self.collection_method_map.get(request.method.lower())
        if not action:
            raise MethodNotAllowed()
        return request_response(action)

    async def _object_view(self, request: Request) -> ASGIApp:
        action = self.object_method_map.get(request.method.lower())
        if not action:
            raise MethodNotAllowed()
        return request_response(action)

    def _is_action_allowed(self, action: str) -> bool:
        if self.only:
            return action in self.only
        if self.exclude:
            return action not in self.exclude
        return True


class Routes(t.Sequence[routing.BaseRoute]):
    def __init__(self, routes: t.Iterable[routing.BaseRoute] = None) -> None:
        self._routes: list[routing.BaseRoute] = list(routes or [])

    def get(
        self,
        path: str,
        endpoint: t.Callable,
        *,
        name: str = None,
        include_in_schema: bool = True,
        middleware: t.Sequence[Middleware] = None,
    ) -> None:
        self.add(
            path,
            endpoint,
            name=name,
            methods=['HEAD', 'GET'],
            include_in_schema=include_in_schema,
            middleware=middleware,
        )

    def post(
        self,
        path: str,
        endpoint: t.Callable,
        *,
        name: str = None,
        include_in_schema: bool = True,
        middleware: t.Sequence[Middleware] = None,
    ) -> None:
        self.add(
            path, endpoint, name=name, methods=['POST'], include_in_schema=include_in_schema, middleware=middleware
        )

    def get_or_post(
        self,
        path: str,
        endpoint: t.Callable,
        *,
        name: str = None,
        include_in_schema: bool = True,
        middleware: t.Sequence[Middleware] = None,
    ) -> None:
        self.add(
            path,
            endpoint,
            name=name,
            methods=['HEAD', 'GET', 'POST'],
            include_in_schema=include_in_schema,
            middleware=middleware,
        )

    def patch(
        self,
        path: str,
        endpoint: t.Callable,
        *,
        name: str = None,
        include_in_schema: bool = True,
        middleware: t.Sequence[Middleware] = None,
    ) -> None:
        self.add(
            path, endpoint, name=name, methods=['PATCH'], include_in_schema=include_in_schema, middleware=middleware
        )

    def put(
        self,
        path: str,
        endpoint: t.Callable,
        *,
        name: str = None,
        include_in_schema: bool = True,
        middleware: t.Sequence[Middleware] = None,
    ) -> None:
        self.add(path, endpoint, name=name, methods=['PUT'], include_in_schema=include_in_schema, middleware=middleware)

    def delete(
        self,
        path: str,
        endpoint: t.Callable,
        *,
        name: str = None,
        include_in_schema: bool = True,
        middleware: t.Sequence[Middleware] = None,
    ) -> None:
        self.add(
            path, endpoint, name=name, methods=['DELETE'], include_in_schema=include_in_schema, middleware=middleware
        )

    def head(
        self,
        path: str,
        endpoint: t.Callable,
        *,
        name: str = None,
        include_in_schema: bool = True,
        middleware: t.Sequence[Middleware] = None,
    ) -> None:
        self.add(
            path, endpoint, name=name, methods=['HEAD'], include_in_schema=include_in_schema, middleware=middleware
        )

    def options(
        self,
        path: str,
        endpoint: t.Callable,
        *,
        name: str = None,
        include_in_schema: bool = True,
        middleware: t.Sequence[Middleware] = None,
    ) -> None:
        self.add(
            path, endpoint, name=name, methods=['OPTIONS'], include_in_schema=include_in_schema, middleware=middleware
        )

    def any(
        self,
        path: str,
        endpoint: t.Callable,
        *,
        name: str = None,
        include_in_schema: bool = True,
        middleware: t.Sequence[Middleware] = None,
    ) -> None:
        _all = ["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "TRACE"]
        self.add(path, endpoint, name=name, methods=_all, include_in_schema=include_in_schema, middleware=middleware)

    def add(
        self,
        path: str,
        endpoint: t.Callable,
        *,
        methods: t.List[str],
        name: str = None,
        include_in_schema: bool = True,
        middleware: t.Sequence[Middleware] = None,
    ) -> None:
        route = Route(
            path,
            endpoint,
            methods=methods,
            name=name,
            include_in_schema=include_in_schema,
            middleware=middleware,
        )
        self._routes.append(route)

    def websocket(self, path: str, endpoint: t.Callable, *, name: str = None) -> None:
        self._routes.append(WebSocketRoute(path, endpoint, name=name))

    def mount(self, path: str, app: ASGIApp, *, name: str = None, middleware: t.Sequence[Middleware] = None) -> None:
        self._routes.append(Mount(path, app, name=name, middleware=middleware))

    def static(
        self,
        path: str,
        directory: t.Union[str, PathLike[str]] = None,
        *,
        packages: list[str] = None,
        html: bool = False,
        check_dir: bool = True,
        name: str = None,
        middleware: t.Sequence[Middleware] = None,
    ) -> None:
        """Serve static files from local directories."""
        app = StaticFiles(directory=directory, packages=packages, html=html, check_dir=check_dir)
        self.mount(path, app, name=name, middleware=middleware)

    def files(
        self, path: str, *, disk: str = None, name: str = None, middleware: t.Sequence[Middleware] = None
    ) -> None:
        """Serve file uploads from disk."""
        app = FileServer(disk=disk)
        self._routes.append(Mount(path, app, name=name, middleware=middleware))

    def host(
        self,
        host: str,
        routes: t.Union[Routes, list[routing.BaseRoute]] = None,
        *,
        name: str = None,
        middleware: t.Sequence[Middleware] = None,
    ) -> HostRoutes:
        app = HostRoutes(host, routes, name, middleware)
        self._routes.append(t.cast(routing.Host, app))
        return app

    def group(
        self,
        prefix: str,
        routes: t.Union[Routes, list[routing.BaseRoute]] = None,
        *,
        name: str = None,
        middleware: t.Sequence[Middleware] = None,
    ) -> GroupRoutes:
        app = GroupRoutes(prefix, routes, name, middleware)
        self._routes.append(t.cast(routing.Mount, app))
        return app

    def redirect(self, path: str, destination: str, status_code: int = 307, headers: dict = None) -> None:
        self.mount(
            path,
            RedirectResponse(destination, status_code=status_code, headers=headers),
        )

    def resource(
        self,
        path: str,
        resource: object,
        *,
        name: str = None,
        only: list[str] = None,
        exclude: list[str] = None,
        include_in_schema: bool = True,
        middleware: t.Sequence[Middleware] = None,
        id_param: str = 'id:int',
    ) -> None:
        self._routes.append(
            ResourceRoute(
                path,
                resource,
                name=name,
                only=only,
                exclude=exclude,
                include_in_schema=include_in_schema,
                middleware=middleware,
                id_param=id_param,
            )
        )

    def api_resource(
        self,
        path: str,
        resource: object,
        *,
        name: str = None,
        only: list[str] = None,
        exclude: list[str] = None,
        include_in_schema: bool = True,
        middleware: t.Sequence[Middleware] = None,
        id_param: str = 'id:int',
    ) -> None:
        excluded = ['new', 'edit']
        only = [action for action in only if action not in excluded] if only else None
        exclude = list({*exclude, *excluded}) if exclude else excluded
        self.resource(
            path,
            resource,
            name=name,
            only=only,
            exclude=exclude,
            include_in_schema=include_in_schema,
            middleware=middleware,
            id_param=id_param,
        )

    def include(
        self, iterable_or_module: t.Union[t.Iterable[routing.BaseRoute], str], callback: str = 'configure'
    ) -> None:
        """Include routes."""
        IncludeRoutesCallback = t.Callable[[Routes], None]
        if isinstance(iterable_or_module, str):
            if ':' not in iterable_or_module:
                iterable_or_module += ':' + callback
            configure_callback: IncludeRoutesCallback = import_string(iterable_or_module)
            configure_callback(self)
        else:
            self._routes.extend(list(iterable_or_module))

    def __iter__(self) -> t.Iterator[routing.BaseRoute]:
        return iter(self._routes)

    def __len__(self) -> int:
        return len(self._routes)

    def __getitem__(self, item: t.Any) -> t.Any:  # pragma: nocover
        """Added to implement Sequence protocol."""
        raise NotImplementedError

    def __contains__(self, route: object) -> t.Any:  # pragma: nocover
        raise NotImplementedError
