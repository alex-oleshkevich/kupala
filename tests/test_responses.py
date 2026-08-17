import typing
from unittest.mock import Mock

import pytest

from kupala.requests import Request
from kupala.responses import BackResponse, Response, response
from tests.types import ScopeFactory


class TestResponseBuilder:
    def test_fluent_methods_clone_and_isolate_state(self) -> None:
        request = typing.cast(Request, Mock())
        builder = response(request)

        authenticated = builder.with_cookie("session", "token")
        logged_out = builder.with_delete_cookie("session")
        overridden = builder.clone(cookies={"override": "value"}, delete_cookies=("old",))
        fluent_clones = (
            builder.with_flash("message", "info"),
            builder.with_vary(),
            builder.with_cache(),
            builder.with_signed_cookie(),
            builder.with_encrypted_cookie(),
        )

        assert authenticated is not builder
        assert logged_out is not builder
        assert overridden is not builder
        assert all(clone is not builder for clone in fluent_clones)

        base_response = builder.text("base", status_code=201, headers={"X-Base": "base"})
        authenticated_response = authenticated.text("authenticated", status_code=201)
        logged_out_response = logged_out.text("logged out", status_code=202)
        overridden_response = overridden.text("overridden")

        assert isinstance(base_response, Response)
        assert base_response.status_code == 201
        assert base_response.headers["X-Base"] == "base"
        assert "set-cookie" not in base_response.headers
        assert authenticated_response.status_code == 201
        assert "session=token" in authenticated_response.headers.getlist("set-cookie")[0]
        assert "session=" in logged_out_response.headers.getlist("set-cookie")[0]
        assert logged_out_response.status_code == 202
        assert "override=value" in overridden_response.headers.getlist("set-cookie")[0]
        assert "old=" in overridden_response.headers.getlist("set-cookie")[1]


class TestBackResponse:
    def test_redirects_to_root_without_a_referer(self, scope_f: ScopeFactory) -> None:
        request = Request(scope_f())
        http_response = response(request).back()

        assert isinstance(http_response, BackResponse)
        assert http_response.status_code == 303
        assert http_response.headers["location"] == "/"

    def test_redirects_to_a_same_origin_referer(self, scope_f: ScopeFactory) -> None:
        request = Request(
            scope_f(
                path="/app/submit",
                root_path="/app",
                headers=[(b"referer", b"http://testserver/app/form?tab=1#details")],
            ),
        )

        assert response(request).back().headers["location"] == "/app/form?tab=1#details"

    @pytest.mark.parametrize(
        ("referer", "root_path"),
        (
            ("https://evil.example/app/form", "/app"),
            ("//evil.example/app/form", "/app"),
            ("https://testserver/app/form", "/app"),
            ("http://testserver:8080/app/form", "/app"),
            ("http://user:password@testserver/app/form", "/app"),
            ("http://testserver:notaport/app/form", "/app"),
            ("http://[invalid/app", "/app"),
            ("app/form", "/app"),
            ("/application/form", "/app"),
            ("/app/../admin", "/app"),
            ("/app/%2e%2e/admin", "/app"),
            ("/app/form%00next", "/app"),
            ("/app/form%20next", "/app"),
            ("/app/form%5cnext", "/app"),
        ),
    )
    def test_rejects_unsafe_or_outside_referers(
        self,
        scope_f: ScopeFactory,
        referer: str,
        root_path: str,
    ) -> None:
        request = Request(
            scope_f(
                path=f"{root_path}/submit",
                root_path=root_path,
                headers=[(b"referer", referer.encode())],
            ),
        )

        assert response(request).back().headers["location"] == root_path

    @pytest.mark.parametrize("referer", ("/app/form\\next", "/app/form\x00next", "/app/form\x1fnext"))
    def test_rejects_referers_with_forbidden_characters(self, scope_f: ScopeFactory, referer: str) -> None:
        request = Request(
            scope_f(
                path="/app/submit",
                root_path="/app",
                headers=[(b"referer", referer.encode())],
            ),
        )

        assert response(request).back().headers["location"] == "/app"

    @pytest.mark.parametrize("root_path", (None, "//evil.example", "/app/../admin", "/app?next=/"))
    def test_rejects_a_malformed_root_path(self, scope_f: ScopeFactory, root_path: typing.Any) -> None:
        request = Request(scope_f(root_path=root_path, path="/submit"))

        assert response(request).back().headers["location"] == "/"

    @pytest.mark.parametrize("status_code", (302, 303))
    def test_accepts_supported_status_codes(self, scope_f: ScopeFactory, status_code: typing.Any) -> None:
        request = Request(scope_f())
        http_response = response(request).back(status_code=status_code)

        assert http_response.status_code == status_code

    def test_preserves_safe_headers_and_applies_cookies(self, scope_f: ScopeFactory) -> None:
        request = Request(scope_f())

        http_response = (
            response(request)
            .with_cookie("session", "token")
            .back(
                headers={"Cache-Control": "public, max-age=3600", "X-Request-ID": "abc"},
            )
        )

        assert http_response.headers["cache-control"] == "no-store"
        assert http_response.headers["x-request-id"] == "abc"
        assert "session=token" in http_response.headers["set-cookie"]

    def test_rejects_status_codes_other_than_302_and_303(self, scope_f: ScopeFactory) -> None:
        request = Request(scope_f())
        invalid_status_codes: tuple[typing.Any, ...] = (301, 307)

        for status_code in invalid_status_codes:
            with pytest.raises(ValueError, match="only supports 302 or 303"):
                response(request).back(status_code=status_code)
