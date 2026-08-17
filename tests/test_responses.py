import typing
from pathlib import Path
from unittest.mock import Mock

import pytest
from markupsafe import Markup
from starlette.datastructures import URLPath
from starlette.types import Receive

from kupala.requests import Request
from kupala.responses import BackResponse, Response, response
from tests.types import ScopeFactory


class TestResponseBuilder:
    def test_renders_a_template_and_applies_cookies(self, scope_f: ScopeFactory) -> None:
        renderer = Mock()
        rendered_response = Response(content="rendered", status_code=201)
        renderer.render_to_response.return_value = rendered_response
        request = Request(scope_f(state={"template_renderer": renderer}))
        context = {"name": "Ada"}
        builder = response(request).with_cookie("session", "token")

        http_response = builder.template(
            "profile.html",
            context,
            status_code=202,
            headers={"X-Test": "yes"},
            media_type="text/plain",
        )

        renderer.render_to_response.assert_called_once_with(
            request,
            "profile.html",
            context,
            status_code=202,
            media_type="text/plain",
            headers={"X-Test": "yes"},
        )
        assert http_response is rendered_response
        assert http_response.body == b"rendered"
        assert "session=token" in http_response.headers["set-cookie"]

    def test_returns_a_text_response(self, scope_f: ScopeFactory) -> None:
        request = Request(scope_f())
        builder = response(request)

        http_response = builder.text(
            "hello",
            status_code=201,
            headers={"X-Test": "yes"},
            media_type="text/markdown",
        )

        assert http_response.status_code == 201
        assert http_response.body == b"hello"
        assert http_response.headers["x-test"] == "yes"
        assert http_response.headers["content-type"] == "text/markdown; charset=utf-8"

    def test_returns_an_empty_response(self, scope_f: ScopeFactory) -> None:
        request = Request(scope_f())
        builder = response(request)

        http_response = builder.empty(headers={"X-Test": "yes"})

        assert http_response.status_code == 204
        assert http_response.body == b""
        assert http_response.headers["x-test"] == "yes"
        assert "content-type" not in http_response.headers

    def test_returns_an_html_response(self, scope_f: ScopeFactory) -> None:
        request = Request(scope_f())
        builder = response(request)

        http_response = builder.html(
            "<p>hello</p>",
            status_code=201,
            headers={"X-Test": "yes"},
            media_type="application/xhtml+xml",
        )

        assert http_response.status_code == 201
        assert http_response.body == b"<p>hello</p>"
        assert http_response.headers["x-test"] == "yes"
        assert http_response.headers["content-type"] == "application/xhtml+xml"

    def test_returns_html_from_an_html_like_value(self, scope_f: ScopeFactory) -> None:
        request = Request(scope_f())
        builder = response(request).with_cookie("session", "token")

        http_response = builder.html(Markup("<strong>trusted</strong>"))

        assert http_response.body == b"<strong>trusted</strong>"
        assert http_response.headers["content-type"] == "text/html; charset=utf-8"
        assert "session=token" in http_response.headers["set-cookie"]

    def test_returns_a_json_response(self, scope_f: ScopeFactory) -> None:
        request = Request(scope_f())
        builder = response(request)

        http_response = builder.json(
            {"ok": True, "items": [1]},
            status_code=202,
            headers={"X-Test": "yes"},
        )

        assert http_response.status_code == 202
        assert http_response.body == b'{"ok":true,"items":[1]}'
        assert http_response.headers["x-test"] == "yes"
        assert http_response.headers["content-type"] == "application/json"

    def test_redirects_to_a_url(self, scope_f: ScopeFactory) -> None:
        request = Request(scope_f())
        builder = response(request)

        http_response = builder.redirect(
            "/target?tab=details#summary",
            status_code=307,
            headers={"X-Test": "yes"},
        )

        assert http_response.status_code == 307
        assert http_response.headers["location"] == "/target?tab=details#summary"
        assert http_response.headers["x-test"] == "yes"

    def test_redirects_to_a_named_route(self, scope_f: ScopeFactory) -> None:
        router = Mock()
        router.url_path_for.return_value = URLPath("/users/42")
        request = Request(scope_f(router=router))
        builder = response(request)

        http_response = builder.redirect_to(
            "user",
            {"user_id": 42},
            status_code=303,
            headers={"X-Test": "yes"},
        )

        router.url_path_for.assert_called_once_with("user", user_id=42)
        assert http_response.status_code == 303
        assert http_response.headers["location"] == "http://testserver/users/42"
        assert http_response.headers["x-test"] == "yes"

    async def test_returns_a_file_response_and_applies_cookies(
        self,
        scope_f: ScopeFactory,
        tmp_path: Path,
    ) -> None:
        file_path = tmp_path / "report.txt"
        file_path.write_bytes(b"report contents")
        request = Request(scope_f())
        builder = response(request).with_cookie("session", "token")

        http_response = builder.file(
            file_path,
            status_code=206,
            headers={"X-Test": "yes"},
            media_type="text/plain",
            filename="report.txt",
            stat_result=file_path.stat(),
            content_disposition="inline",
        )
        messages: list[typing.Any] = []

        receive = typing.cast(Receive, Mock())

        async def send(message: typing.Any) -> None:
            messages.append(message)

        await http_response(scope_f(), receive, send)

        body = b"".join(message["body"] for message in messages if message["type"] == "http.response.body")
        assert http_response.status_code == 206
        assert http_response.headers["x-test"] == "yes"
        assert http_response.headers["content-type"] == "text/plain; charset=utf-8"
        assert http_response.headers["content-length"] == "15"
        assert http_response.headers["content-disposition"] == 'inline; filename="report.txt"'
        assert "session=token" in http_response.headers["set-cookie"]
        assert body == b"report contents"

    async def test_streams_sync_content_and_applies_cookies(self, scope_f: ScopeFactory) -> None:
        def chunks() -> typing.Iterator[str]:
            yield "hello"
            yield " world"

        request = Request(scope_f())
        builder = response(request).with_cookie("session", "token")
        http_response = builder.stream(
            chunks(),
            status_code=206,
            headers={"X-Test": "yes"},
            media_type="text/plain",
        )
        messages: list[typing.Any] = []

        receive = typing.cast(Receive, Mock())

        async def send(message: typing.Any) -> None:
            messages.append(message)

        await http_response(scope_f(), receive, send)

        body = b"".join(message["body"] for message in messages if message["type"] == "http.response.body")
        assert http_response.status_code == 206
        assert http_response.headers["x-test"] == "yes"
        assert http_response.headers["content-type"] == "text/plain; charset=utf-8"
        assert "session=token" in http_response.headers["set-cookie"]
        assert body == b"hello world"

    def test_returns_an_sse_response(self, scope_f: ScopeFactory) -> None:
        request = Request(scope_f())
        builder = response(request).with_cookie("session", "token")

        http_response = builder.sse(status_code=201, headers={"X-Test": "yes"})

        assert http_response.status_code == 201
        assert http_response.headers["x-test"] == "yes"
        assert "session=token" in http_response.headers["set-cookie"]

    def test_fluent_methods_clone_and_isolate_state(self) -> None:
        request = typing.cast(Request, Mock())
        builder = response(request)

        authenticated = builder.with_cookie("session", "token")
        logged_out = builder.with_delete_cookie("session")
        overridden = builder.clone(cookies={"override": "value"}, delete_cookies=("old",))
        fluent_clones = (
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
