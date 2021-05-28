from __future__ import annotations

import pathlib
import typing as t
from unittest import mock

from starlette import routing
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import URLPath
from starlette.routing import Match, iscoroutinefunction_or_partial
from starlette.staticfiles import StaticFiles
from starlette.types import ASGIApp, Receive, Scope, Send

from kupala.middleware import MiddlewareStack
from kupala.utils import import_string

from . import responses


def request_response(func: t.Callable) -> ASGIApp:
    """
    Takes a function or coroutine `func(request) -> response`,
    and returns an ASGI application.
    """
    is_coroutine = iscoroutinefunction_or_partial(func)

    async def app(scope: Scope, receive: Receive, send: Send) -> None:
        request = scope["request"]
        if is_coroutine:
            response = await request.app.invoke(func, request=request)
        else:
            response = await run_in_threadpool(
                request.app.invoke,
                func,
                request=request,
            )

        await response(scope, receive, send)

    return app


class Router(routing.Router):
    ...


class Route(routing.Route):
    def __init__(
        self,
        path: str,
        endpoint: t.Callable,
        *,
        methods: list[str] = None,
        name: str = None,
        include_in_schema: bool = True,
    ) -> None:
        with mock.patch("starlette.routing.request_response", request_response):
            super().__init__(
                path,
                endpoint,
                methods=methods,
                name=name,
                include_in_schema=include_in_schema,
            )


class Mount(routing.Mount):
    ...


class WebSocketRoute(routing.WebSocketRoute):
    ...


class Redirect:
    def __init__(self, destination: str, status_code: int = 302) -> None:
        self.redirect_slashes = False
        self.destination = destination
        self.status_code = status_code

    async def __call__(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
    ) -> None:
        response = responses.RedirectResponse(
            scope["request"],
            self.destination,
            self.status_code,
        )
        await response(scope, receive, send)


class Host(routing.BaseRoute):
    def __init__(self, host: str, middleware: list[str] = None):
        self.host = host
        self.middleware = middleware or []
        self.routes = Routes()
        self.host_app: t.Optional[routing.Host] = None
        self.host_app_with_middleware: t.Optional[ASGIApp] = None

    async def handle(self, scope: Scope, receive: Receive, send: Send) -> None:
        host_app = t.cast(ASGIApp, self._get_host_app())
        if self.host_app_with_middleware is None:
            stack: MiddlewareStack = scope["app"].middleware
            for group in self.middleware:
                if not stack.has_group(group):
                    raise KeyError('Middleware group "%s" is not defined.' % (group,))
                for middleware in reversed(stack.group(group)):
                    host_app = middleware.wrap(host_app)
            self.host_app_with_middleware = host_app
        await self.host_app_with_middleware(scope, receive, send)

    def matches(self, scope: Scope) -> t.Tuple[Match, Scope]:
        return self._get_host_app().matches(scope)

    def url_path_for(self, name: str, **path_params: str) -> URLPath:
        return self._get_host_app().url_path_for(name, **path_params)

    def _get_host_app(self) -> routing.Host:
        if self.host_app is None:
            self.host_app = routing.Host(self.host, Router(self.routes))
        return self.host_app

    def __enter__(self) -> Routes:
        return self.routes

    def __exit__(self, *args: t.Any) -> None:
        pass


class Group:
    """Group multiple similar routes under a common path.

    The routes can be wrapped into middleware.
    These middleware are defined on application level
    and grouped by a string key.
    """

    def __init__(self, middleware_groups: list[str] = None) -> None:
        self.middleware_groups = middleware_groups or []
        self.routes = Routes()
        self.wrapped_app: t.Optional[ASGIApp] = None

    def __enter__(self) -> Routes:
        return self.routes

    def __exit__(self, *args: t.Any) -> None:
        pass

    async def __call__(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
    ) -> None:
        if self.wrapped_app is None:
            self.wrapped_app = Router(self.routes)
            stack: MiddlewareStack = scope["app"].middleware
            for group in self.middleware_groups:
                for middleware in reversed(stack.group(group)):
                    self.wrapped_app = middleware.wrap(self.wrapped_app)

        assert self.wrapped_app
        return await self.wrapped_app(scope, receive, send)


class Routes(t.Sequence[routing.BaseRoute]):
    def __init__(self) -> None:
        self._routes: list[routing.BaseRoute] = []

    def get(
        self,
        path: str,
        endpoint: t.Callable,
        name: str = None,
    ) -> None:
        """Make endpoint to respond to GET requests."""
        self.add(path, endpoint, ["GET"], name)

    def post(
        self,
        path: str,
        endpoint: t.Callable,
        name: str = None,
    ) -> None:
        """Make endpoint to respond to POST requests."""
        self.add(path, endpoint, ["POST"], name)

    def put(
        self,
        path: str,
        endpoint: t.Callable,
        name: str = None,
    ) -> None:
        """Make endpoint to respond to PUT requests."""
        self.add(path, endpoint, ["PUT"], name)

    def patch(
        self,
        path: str,
        endpoint: t.Callable,
        name: str = None,
    ) -> None:
        """Make endpoint to respond to PATCH requests."""
        self.add(path, endpoint, ["PATCH"], name)

    def delete(
        self,
        path: str,
        endpoint: t.Callable,
        name: str = None,
    ) -> None:
        """Make endpoint to respond to DELETE requests."""
        self.add(path, endpoint, ["DELETE"], name)

    def options(
        self,
        path: str,
        endpoint: t.Callable,
        name: str = None,
    ) -> None:
        """Make endpoint to respond to OPTIONS requests."""
        self.add(path, endpoint, ["OPTIONS"], name)

    def any(self, path: str, endpoint: t.Callable, name: str = None) -> None:
        """Make endpoint to respond to any request method."""
        _all = ["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]
        self.add(path, endpoint, _all, name)

    def get_or_post(
        self,
        path: str,
        endpoint: t.Callable,
        name: str = None,
    ) -> None:
        """Make endpoint to respond to POST or GET requests."""
        self.add(path, endpoint, ["POST", "GET"], name)

    def add(
        self,
        path: str,
        endpoint: t.Callable,
        methods: t.Optional[list[str]] = None,
        name: str = None,
    ) -> None:
        """Add an endpoint."""
        self._routes.append(Route(path, endpoint=endpoint, methods=methods, name=name))

    def websocket(
        self,
        path: str,
        endpoint: t.Callable,
        name: str = None,
    ) -> None:
        """Add websocket endpoint."""
        self._routes.append(WebSocketRoute(path, endpoint, name=name))

    def group(
        self,
        path: str,
        middleware: list[str] = None,
    ) -> Group:
        """Group groups by a common path.
        Optionally, apply a list of middleware on this group.
        These middleware will be called before calling the endpoint."""
        group = Group(middleware)
        self.mount(path, group)
        return group

    def redirect(
        self,
        from_: str,
        destination: str,
        status_code: int = 302,
    ) -> None:
        """Redirect client from one route to another."""
        self.mount(
            from_,
            Redirect(destination=destination, status_code=status_code),
        )

    def host(
        self,
        domain: str,
        middleware: list[str] = None,
    ) -> Host:
        """Group groups by a subdomain.

        Optionally, apply a list of middleware on this group.
        These middleware will be called before calling the endpoint."""
        subdomain = Host(domain, middleware)
        self._routes.append(subdomain)
        return subdomain

    def mount(self, path: str, app: ASGIApp, name: str = None) -> None:
        """Mount any ASGI compliant object."""
        self._routes.append(Mount(path, app=app, name=name))

    def static(self, path: str, directory: t.Union[str, pathlib.Path]) -> None:
        self.mount(path, StaticFiles(directory=str(directory)))

    def include(self, module_name: str, callback: str = "configure") -> None:
        fn_path = module_name + "." + callback
        fn = import_string(fn_path)
        fn(self)

    load_from_callback = include

    def __iter__(self) -> t.Iterator[routing.BaseRoute]:
        return iter(self._routes)

    def __len__(self) -> int:
        return len(self._routes)

    @t.overload  # pragma: no cover
    def __getitem__(self, i: int) -> routing.BaseRoute:  # noqa: F811
        ...

    @t.overload  # pragma: no cover
    def __getitem__(self, s: slice) -> t.Sequence[routing.BaseRoute]:  # noqa: F811
        ...

    def __getitem__(  # noqa: F811
        self, index: t.Union[int, slice]
    ) -> t.Union[routing.BaseRoute, t.Sequence[routing.BaseRoute]]:
        """Not used, only here to match the interface of Sequence type.
        The router requires routes to be of Sequence type, this class
        mimics to the Sequence and therefore must implement __getitem__."""
        return self._routes[index]


class RouteURLResolver:
    def __init__(self, router: Router):
        self.router = router

    def resolve(self, name: str, **path_params: str) -> routing.URLPath:
        return self.router.url_path_for(name, **path_params)
