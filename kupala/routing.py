from __future__ import annotations

import pathlib
import typing as t

from starlette import routing
from starlette.staticfiles import StaticFiles
from starlette.types import ASGIApp
from starlette.types import Receive
from starlette.types import Scope
from starlette.types import Send

from . import responses
from kupala.middleware import MiddlewareStack
from kupala.utils import import_string


class Router(routing.Router):
    ...


class Route(routing.Route):
    ...


class Mount(routing.Mount):
    ...


class WebSocket(routing.WebSocketRoute):
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
            self.destination,
            self.status_code,
        )
        await response(scope, receive, send)


class Host:
    """Groups routes under a subdomain."""

    def __init__(
        self,
        domain: str,
        middleware_groups: list[str] = None,
    ) -> None:
        self.middleware_groups = middleware_groups or []
        self.routes = Routes()
        self.domain = domain
        self.wrapped_app: t.Optional[ASGIApp] = None
        self.host_app: t.Optional[routing.Host] = None

    @property
    def app(self) -> routing.Host:
        if self.host_app is None:
            self.host_app = routing.Host(
                self.domain,
                Router(list(self.routes)),
            )
        return self.host_app

    async def handle(self, scope: Scope, receive: Receive, send: Send) -> None:
        await self(scope, receive, send)

    def __getattr__(self, item: str) -> t.Any:
        return getattr(self.app, item)

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
            self.wrapped_app = self.app
            stack: MiddlewareStack = scope["app"].middleware
            for group in self.middleware_groups:
                for middleware in reversed(stack.group(group)):
                    self.wrapped_app = middleware.wrap(self.wrapped_app)

        assert self.wrapped_app
        return await self.wrapped_app(scope, receive, send)


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
            self.wrapped_app = Router(list(self.routes))
            stack: MiddlewareStack = scope["app"].middleware
            for group in self.middleware_groups:
                for middleware in reversed(stack.group(group)):
                    self.wrapped_app = middleware.wrap(self.wrapped_app)

        assert self.wrapped_app
        return await self.wrapped_app(scope, receive, send)


class Routes:
    def __init__(self) -> None:
        self._routes: list[t.Union[routing.BaseRoute, ASGIApp]] = []

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
        self._routes.append(WebSocket(path, endpoint, name=name))

    def group(
        self,
        path: str,
        middleware: t.Union[str, list[str]] = None,
    ) -> Group:
        """Group groups by a common path.
        Optionally, apply a list of middleware on this group.
        These middleware will be called before calling the endpoint."""
        if isinstance(middleware, str):
            middleware = [middleware]
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
        middleware: t.Union[str, list[str]] = None,
    ) -> Host:
        """Group groups by a subdomain.

        Optionally, apply a list of middleware on this group.
        These middleware will be called before calling the endpoint."""
        if isinstance(middleware, str):
            middleware = [middleware]
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

    def __enter__(self) -> Routes:
        return self

    def __exit__(self, *args: t.Any) -> None:
        pass

    def __iter__(self) -> t.Iterator[routing.BaseRoute]:
        return iter(self._routes)

    def __len__(self) -> int:
        return len(self._routes)

    def __getitem__(self, index: int) -> t.Union[routing.BaseRoute, ASGIApp]:
        return self._routes[index]
