"""A documented group of routes that installs itself into an application."""

import dataclasses
import secrets
import typing

from kupala.api.generator import build_document
from kupala.api.schema_generators import SchemaGenerator
from kupala.api.security import SecurityScheme
from kupala.extensions import AppBuilder
from kupala.middleware import Middleware
from kupala.openapi import Info, OpenAPI, to_dict
from kupala.requests import Request
from kupala.responses import Response, response
from kupala.routing import Routes, join_namespace

__all__ = ["REDOC_BASE_URL", "SCALAR_BASE_URL", "SWAGGER_BASE_URL", "APIExtension", "DocsOptions"]

SPEC_ROUTE_NAME: typing.Final = "kupala.openapi.json"
SWAGGER_ROUTE_NAME: typing.Final = "kupala.openapi.swagger"
REDOC_ROUTE_NAME: typing.Final = "kupala.openapi.redoc"
SCALAR_ROUTE_NAME: typing.Final = "kupala.openapi.scalar"

SWAGGER_BASE_URL: typing.Final = "https://cdn.jsdelivr.net/npm/swagger-ui-dist@5.29.4"
REDOC_BASE_URL: typing.Final = "https://cdn.jsdelivr.net/npm/redoc@2.5.0/bundles"
SCALAR_BASE_URL: typing.Final = "https://cdn.jsdelivr.net/npm/@scalar/api-reference@1.68.0/dist/browser"

DEFAULT_INFO: typing.Final = Info(title="API", version="0.0.0")


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class DocsOptions:
    """Which documentation endpoints exist, and where each viewer's assets come from."""

    openapi_path: str | None = None
    swagger_path: str | None = None
    redoc_path: str | None = None
    scalar_path: str | None = None
    swagger_base_url: str = SWAGGER_BASE_URL
    redoc_base_url: str = REDOC_BASE_URL
    scalar_base_url: str = SCALAR_BASE_URL


class APIExtension:
    """A group of documented routes, contributed to an application through `Extension.install`."""

    def __init__(
        self,
        prefix: str,
        *,
        namespace: str = "",
        docs: DocsOptions | None = None,
        routes: Routes | None = None,
        openapi: OpenAPI | None = None,
        tags: typing.Sequence[str] = (),
        schema_generators: typing.Sequence[SchemaGenerator] = (),
        security: typing.Sequence[SecurityScheme[typing.Any]] = (),
        middleware: typing.Sequence[Middleware] = (),
    ) -> None:
        self.docs = docs or DocsOptions()
        self.openapi = openapi or OpenAPI(info=DEFAULT_INFO)
        self.security = security
        self.schema_generators = schema_generators
        self.routes = Routes(
            prefix=prefix,
            namespace=namespace,
            tags=tags,
            middleware=middleware,
            children=(routes,) if routes is not None else (),
        )
        # a compiled route name carries the namespace of the group that declared it
        self.spec_route_name = join_namespace(namespace, SPEC_ROUTE_NAME)
        self._document: OpenAPI | None = None

        ui_paths = (self.docs.swagger_path, self.docs.redoc_path, self.docs.scalar_path)
        if self.docs.openapi_path is None and any(path is not None for path in ui_paths):
            raise ValueError("A documentation UI reads the document over HTTP, so `openapi_path` must be set too.")

        # `openapi=None` leaves each of these out of the document: the documentation is not the API
        if self.docs.openapi_path is not None:
            self.routes.add(self.docs.openapi_path, self.openapi_view, methods=["GET"], name=SPEC_ROUTE_NAME)
        if self.docs.swagger_path is not None:
            self.routes.add(self.docs.swagger_path, self.swagger_view, methods=["GET"], name=SWAGGER_ROUTE_NAME)
        if self.docs.redoc_path is not None:
            self.routes.add(self.docs.redoc_path, self.redoc_view, methods=["GET"], name=REDOC_ROUTE_NAME)
        if self.docs.scalar_path is not None:
            self.routes.add(self.docs.scalar_path, self.scalar_view, methods=["GET"], name=SCALAR_ROUTE_NAME)

    def install(self, builder: AppBuilder) -> None:
        builder.routes.include(self.routes)

    def document(self) -> OpenAPI:
        """Describe the registered routes, generating the document once."""

        if self._document is None:
            self._document = build_document(self.routes, self.openapi)
        return self._document

    async def openapi_view(self, request: Request) -> Response:
        return response(request).json(to_dict(self.document()), headers={"x-content-type-options": "nosniff"})

    async def swagger_view(self, request: Request) -> Response:
        return self._page(request, "openapi/swagger.html.j2", self.docs.swagger_base_url)

    async def redoc_view(self, request: Request) -> Response:
        return self._page(request, "openapi/redoc.html.j2", self.docs.redoc_base_url)

    async def scalar_view(self, request: Request) -> Response:
        return self._page(request, "openapi/scalar.html.j2", self.docs.scalar_base_url)

    def _page(self, request: Request, template_name: str, base_url: str) -> Response:
        """Render one viewer, pointed at the document by the route name that serves it."""

        # a viewer is a third party running script beside a button that sends real credentials, so the
        # policy names its one host and nothing else. Styles cannot use the nonce: viewers inject theirs
        nonce = secrets.token_urlsafe(16)
        # normalised once: the templates append a rooted path to this, and a trailing slash would double
        base_url = base_url.rstrip("/")
        # a source expression covers a directory only when its path ends in a slash, and a path carrying
        # no host is not a source expression at all, so a copy served from here is covered by 'self'
        absolute = base_url.startswith(("https://", "http://", "//"))
        source = f"{base_url}/" if absolute else "'self'"
        policy = "; ".join(
            (
                "default-src 'none'",
                f"script-src {source} 'nonce-{nonce}'",
                # Redoc indexes the document for search in a worker it builds as a blob, and a script
                # already allowed to run gains nothing by moving itself into one
                "worker-src blob:",
                f"style-src {source} 'unsafe-inline'",
                f"img-src data: {source}",
                f"font-src {source}",
                "connect-src 'self'",
                "base-uri 'none'",
                "form-action 'none'",
                "frame-ancestors 'none'",
            )
        )
        return response(request).template(
            template_name,
            {
                # resolved by name, never built from a prefix: the only form that survives a root path
                "spec_url": str(request.url_for(self.spec_route_name)),
                "title": self.openapi.info.title,
                "base_url": base_url,
                "nonce": nonce,
            },
            headers={
                "content-security-policy": policy,
                "x-content-type-options": "nosniff",
                "referrer-policy": "no-referrer",
            },
        )
