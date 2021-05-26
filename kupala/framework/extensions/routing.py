from kupala.application import App
from kupala.contracts import URLResolver
from kupala.extensions import Extension
from kupala.routing import Router, Routes, RouteURLResolver


class RoutingExtension(Extension):
    def __init__(self, redirect_slashes: bool = True) -> None:
        self.redirect_slashes = redirect_slashes

    def register(self, app: App) -> None:
        app.singleton(Router, self._create_router, aliases="router")
        app.singleton(
            URLResolver,
            self._create_url_resolver,
            aliases=[
                "url_resolver",
                "route_url_resolver",
                RouteURLResolver,
            ],
        )

    def _create_router(self, app: App) -> Router:
        return Router(
            routes=app.get(Routes),
            redirect_slashes=self.redirect_slashes,
            lifespan=app.lifespan,
        )

    def _create_url_resolver(self, router: Router) -> RouteURLResolver:
        return RouteURLResolver(router)
