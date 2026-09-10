import re
import typing

import jinja2
import pytest
from starlette.routing import Route
from starlette.testclient import TestClient

from kupala.api import (
    REDOC_BASE_URL,
    SCALAR_BASE_URL,
    SWAGGER_BASE_URL,
    APIExtension,
    DocsOptions,
)
from kupala.applications import Kupala
from kupala.extensions import AppBuilder
from kupala.middleware import CallNext
from kupala.requests import Request
from kupala.responses import Response
from kupala.routing import Routes
from kupala.schema.builder import DuplicateOperationError
from kupala.schema.openapi import Info, OpenAPI
from kupala.templates import Templates

ALL_DOCS = DocsOptions(
    openapi_path="/openapi.json",
    swagger_path="/docs",
    redoc_path="/redoc",
    scalar_path="/scalar",
)
UI_PATHS = ("/api/docs", "/api/redoc", "/api/scalar")


def demo_routes() -> Routes:
    routes = Routes(tags=["users"])

    @routes.get("/users")
    async def list_users(request: Request) -> Response:
        """List users.

        Everything the caller may see.
        """
        return Response("[]")

    @routes.delete("/users/{id:int}")
    async def delete_user(request: Request) -> Response:
        return Response(status_code=204)  # pragma: no cover

    return routes


class TestDocumentationIsOptional:
    def test_registers_no_routes_by_default(self) -> None:
        api = APIExtension("/api")

        assert api.routes.definitions == []

    def test_a_ui_without_the_document_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="openapi_path"):
            APIExtension("/api", docs=DocsOptions(swagger_path="/docs"))

    def test_the_document_alone_needs_no_ui(self) -> None:
        api = APIExtension("/api", docs=DocsOptions(openapi_path="/openapi.json"))
        app = Kupala("tests", routes=Routes(), extensions=[api])

        with TestClient(app) as client:
            assert client.get("/api/openapi.json").status_code == 200
            assert client.get("/api/docs").status_code == 404


class TestDocument:
    def test_serves_the_described_routes(self) -> None:
        api = APIExtension(
            "/api",
            routes=demo_routes(),
            openapi=OpenAPI(info=Info(title="Demo", version="1.2.3")),
            docs=DocsOptions(openapi_path="/openapi.json"),
        )
        app = Kupala("tests", routes=Routes(), extensions=[api])

        with TestClient(app) as client:
            document = client.get("/api/openapi.json").json()

        assert document["openapi"] == "3.1.1"
        assert document["info"] == {"title": "Demo", "version": "1.2.3"}
        assert sorted(document["paths"]) == ["/api/users", "/api/users/{id}"]
        assert document["paths"]["/api/users"]["get"]["summary"] == "List users."
        assert document["paths"]["/api/users"]["get"]["tags"] == ["users"]

    def test_leaves_the_documentation_routes_out_of_itself(self) -> None:
        api = APIExtension("/api", routes=demo_routes(), docs=ALL_DOCS)

        assert sorted(api.document().paths or {}) == ["/api/users", "/api/users/{id}"]

    def test_a_route_it_cannot_describe_stops_the_application_starting(self) -> None:
        # a document that cannot be built is a mistake in the application, not in the request that
        # happened to ask for it first
        async def view(request: Request) -> Response:
            return Response("")  # pragma: no cover - the document never gets built

        routes = Routes()
        routes.get("/a", name="a", operation_id="same")(view)
        routes.get("/b", name="b", operation_id="same")(view)
        api = APIExtension("/api", routes=routes, docs=DocsOptions(openapi_path="/openapi.json"))
        app = Kupala("tests", routes=Routes(), extensions=[api])

        with pytest.raises(DuplicateOperationError, match="'same' describes both"), TestClient(app):
            pass  # pragma: no cover - the lifespan raises before the block runs

    def test_is_rendered_before_the_first_request(self) -> None:
        api = APIExtension("/api", routes=demo_routes(), docs=DocsOptions(openapi_path="/openapi.json"))
        app = Kupala("tests", routes=Routes(), extensions=[api])

        with TestClient(app) as client:
            rendered = api.serialize()
            assert client.get("/api/openapi.json").content == rendered
            # the bytes are handed out, never rebuilt
            assert api.serialize() is rendered

    def test_is_generated_once(self) -> None:
        api = APIExtension("/api", routes=demo_routes())

        assert api.document() is api.document()

    def test_names_itself_when_no_info_is_given(self) -> None:
        api = APIExtension("/api", docs=DocsOptions(openapi_path="/openapi.json"))
        app = Kupala("tests", routes=Routes(), extensions=[api])

        with TestClient(app) as client:
            assert client.get("/api/openapi.json").json()["info"] == {"title": "API", "version": "0.0.0"}

    def test_is_served_without_content_sniffing(self) -> None:
        api = APIExtension("/api", docs=DocsOptions(openapi_path="/openapi.json"))
        app = Kupala("tests", routes=Routes(), extensions=[api])

        with TestClient(app) as client:
            response = client.get("/api/openapi.json")

        assert response.headers["content-type"] == "application/json"
        assert response.headers["x-content-type-options"] == "nosniff"


class TestPages:
    @pytest.mark.parametrize("path", UI_PATHS)
    def test_renders_a_viewer_pointed_at_the_document(self, path: str) -> None:
        api = APIExtension(
            "/api",
            openapi=OpenAPI(info=Info(title="Demo", version="1.2.3")),
            docs=ALL_DOCS,
        )
        app = Kupala("tests", routes=Routes(), extensions=[api])

        with TestClient(app) as client:
            response = client.get(path)

        assert response.status_code == 200
        assert "<title>Demo</title>" in response.text
        assert '"http://testserver/api/openapi.json"' in response.text

    @pytest.mark.parametrize("path", UI_PATHS)
    def test_the_only_script_allowed_to_run_is_the_one_we_wrote(self, path: str) -> None:
        api = APIExtension("/api", docs=ALL_DOCS)
        app = Kupala("tests", routes=Routes(), extensions=[api])

        with TestClient(app) as client:
            response = client.get(path)

        nonce = re.search(r'<script nonce="([^"]+)">', response.text)
        assert nonce is not None
        assert f"'nonce-{nonce.group(1)}'" in response.headers["content-security-policy"]

    @pytest.mark.parametrize("path", UI_PATHS)
    def test_a_nonce_is_never_reused(self, path: str) -> None:
        api = APIExtension("/api", docs=ALL_DOCS)
        app = Kupala("tests", routes=Routes(), extensions=[api])

        with TestClient(app) as client:
            policies = {client.get(path).headers["content-security-policy"] for _ in range(2)}

        assert len(policies) == 2

    @pytest.mark.parametrize("path", UI_PATHS)
    def test_each_viewer_loads_from_its_own_pinned_host(self, path: str) -> None:
        api = APIExtension("/api", docs=ALL_DOCS)
        app = Kupala("tests", routes=Routes(), extensions=[api])

        with TestClient(app) as client:
            response = client.get(path)

        base_url = {
            "/api/docs": ALL_DOCS.swagger_base_url,
            "/api/redoc": ALL_DOCS.redoc_base_url,
            "/api/scalar": ALL_DOCS.scalar_base_url,
        }[path]
        assert f'src="{base_url}/' in response.text
        assert response.headers["content-security-policy"].count(base_url) == 4

    def test_locks_the_page_down_to_the_one_host_it_needs(self) -> None:
        api = APIExtension(
            "/api",
            docs=DocsOptions(
                openapi_path="/openapi.json",
                swagger_path="/docs",
                swagger_base_url="https://cdn.example.com/ui@1.2",
            ),
        )
        app = Kupala("tests", routes=Routes(), extensions=[api])

        with TestClient(app) as client:
            response = client.get("/api/docs")

        nonce = re.search(r'<script nonce="([^"]+)">', response.text)
        assert nonce is not None
        assert response.headers["content-security-policy"] == "; ".join(
            (
                "default-src 'none'",
                f"script-src https://cdn.example.com/ui@1.2/ 'nonce-{nonce.group(1)}'",
                "worker-src blob:",
                "style-src https://cdn.example.com/ui@1.2/ 'unsafe-inline'",
                "img-src data: https://cdn.example.com/ui@1.2/",
                "font-src https://cdn.example.com/ui@1.2/",
                "connect-src 'self'",
                "base-uri 'none'",
                "form-action 'none'",
                "frame-ancestors 'none'",
            )
        )

    @pytest.mark.parametrize("path", UI_PATHS)
    def test_the_viewer_source_covers_the_directory_it_loads_from(self, path: str) -> None:
        # a source expression without a trailing slash matches one exact path, so the viewer's own
        # files are refused by the browser while the policy still looks correct
        api = APIExtension("/api", docs=ALL_DOCS)
        app = Kupala("tests", routes=Routes(), extensions=[api])

        with TestClient(app) as client:
            response = client.get(path)

        asset = re.search(r'src="([^"]+)"', response.text)
        assert asset is not None
        source = re.findall(r"script-src (\S+) ", response.headers["content-security-policy"])
        assert source and asset.group(1).startswith(source[0])

    @pytest.mark.parametrize("path", UI_PATHS)
    def test_carries_the_sniffing_and_referrer_defences(self, path: str) -> None:
        api = APIExtension("/api", docs=ALL_DOCS)
        app = Kupala("tests", routes=Routes(), extensions=[api])

        with TestClient(app) as client:
            response = client.get(path)

        assert response.headers["x-content-type-options"] == "nosniff"
        assert response.headers["referrer-policy"] == "no-referrer"

    def test_a_self_hosted_viewer_replaces_the_cdn_everywhere(self) -> None:
        api = APIExtension(
            "/api",
            docs=DocsOptions(openapi_path="/openapi.json", swagger_path="/docs", swagger_base_url="/static/swagger"),
        )
        app = Kupala("tests", routes=Routes(), extensions=[api])

        with TestClient(app) as client:
            response = client.get("/api/docs")

        assert "cdn.jsdelivr.net" not in response.text
        assert 'src="/static/swagger/swagger-ui-bundle.js"' in response.text
        assert "//swagger-ui-bundle.js" not in response.text
        # a path carrying no host is not a source expression a browser accepts, so this origin is named
        assert "script-src 'self' " in response.headers["content-security-policy"]
        assert "/static/swagger" not in response.headers["content-security-policy"]

    def test_a_trailing_slash_on_the_base_url_changes_nothing(self) -> None:
        api = APIExtension(
            "/api",
            docs=DocsOptions(
                openapi_path="/openapi.json",
                swagger_path="/docs",
                swagger_base_url="https://cdn.example.com/ui/",
            ),
        )
        app = Kupala("tests", routes=Routes(), extensions=[api])

        with TestClient(app) as client:
            response = client.get("/api/docs")

        assert 'src="https://cdn.example.com/ui/swagger-ui-bundle.js"' in response.text
        assert "script-src https://cdn.example.com/ui/ " in response.headers["content-security-policy"]

    def test_the_document_url_follows_the_root_path(self) -> None:
        api = APIExtension("/api", docs=ALL_DOCS)
        app = Kupala("tests", routes=Routes(), extensions=[api])

        with TestClient(app, root_path="/behind") as client:
            response = client.get("/api/docs")

        assert '"http://testserver/behind/api/openapi.json"' in response.text

    def test_the_document_url_follows_the_namespace(self) -> None:
        api = APIExtension("/api", namespace="v1", docs=ALL_DOCS)
        app = Kupala("tests", routes=Routes(), extensions=[api])

        with TestClient(app) as client:
            response = client.get("/api/docs")

        assert '"http://testserver/api/openapi.json"' in response.text

    @pytest.mark.parametrize("template_name", ["swagger", "redoc", "scalar"])
    def test_a_url_reaches_a_script_as_a_javascript_literal(self, template_name: str) -> None:
        # html escaping is the wrong escaping inside a script element, where `</script>` ends the element
        templates = Templates(packages=["kupala"])

        page = templates.render(
            f"openapi/{template_name}.html.j2",
            {"title": "t", "spec_url": "</script><script>alert(1)</script>", "base_url": "/s", "nonce": "n"},
        )

        assert "<script>alert(1)" not in page
        assert "\\u003cscript\\u003ealert(1)" in page

    def test_a_title_cannot_break_out_of_the_page(self) -> None:
        api = APIExtension("/api", openapi=OpenAPI(info=Info(title="A & B </script>", version="1")), docs=ALL_DOCS)
        app = Kupala("tests", routes=Routes(), extensions=[api])

        with TestClient(app) as client:
            response = client.get("/api/docs")

        assert "</script>" not in response.text.split("<title>")[1].split("</title>")[0]
        assert "<title>A &amp; B &lt;/script&gt;</title>" in response.text


def test_every_viewer_is_pinned_to_one_version() -> None:
    for base_url in (SWAGGER_BASE_URL, REDOC_BASE_URL, SCALAR_BASE_URL):
        assert "@" in base_url.removeprefix("https://cdn.jsdelivr.net/npm/")


class TestInstall:
    def test_contributes_its_routes(self) -> None:
        api = APIExtension("/api", docs=ALL_DOCS)
        builder = AppBuilder()

        api.install(builder)

        routes = [typing.cast(Route, route) for route in builder.routes.compile((), (), ())]
        assert [(route.path, route.name) for route in routes] == [
            ("/api/openapi.json", "kupala.openapi.json"),
            ("/api/docs", "kupala.openapi.swagger"),
            ("/api/redoc", "kupala.openapi.redoc"),
            ("/api/scalar", "kupala.openapi.scalar"),
        ]

    def test_an_application_page_outranks_the_shipped_one(self) -> None:
        api = APIExtension("/api", docs=ALL_DOCS)
        templates = Templates(loaders=[jinja2.DictLoader({"openapi/swagger.html.j2": "ours"})])
        app = Kupala("tests", routes=Routes(), templates=templates, extensions=[api])

        with TestClient(app) as client:
            assert client.get("/api/docs").text == "ours"

    def test_routes_given_to_the_api_answer_under_its_prefix(self) -> None:
        api = APIExtension("/api", routes=demo_routes())
        app = Kupala("tests", routes=Routes(), extensions=[api])

        with TestClient(app) as client:
            assert client.get("/api/users").text == "[]"

    def test_middleware_wraps_the_documented_routes(self) -> None:
        seen: list[str] = []

        async def audit(request: Request, call_next: CallNext) -> Response:
            seen.append(request.url.path)
            return await call_next(request)

        api = APIExtension("/api", routes=demo_routes(), docs=ALL_DOCS, middleware=[audit])
        app = Kupala("tests", routes=Routes(), extensions=[api])

        with TestClient(app) as client:
            client.get("/api/users")
            client.get("/api/docs")

        assert seen == ["/api/users", "/api/docs"]
