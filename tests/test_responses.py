import typing
from pathlib import Path
from unittest.mock import Mock

import anyio
import pytest
from markupsafe import Markup
from starlette.datastructures import URLPath
from starlette.requests import ClientDisconnect
from starlette.types import Receive

from kupala.requests import Request
from kupala.responses import BackResponse, Response, ServerSentEvent, SSEResponse, response
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

        http_response = builder.sse(
            [ServerSentEvent(data="hello")],
            status_code=201,
            headers={"X-Test": "yes"},
            keepalive_interval=None,
        )

        assert isinstance(http_response, SSEResponse)
        assert http_response.keepalive_interval is None
        assert http_response.status_code == 201
        assert http_response.headers["x-test"] == "yes"
        assert http_response.headers["content-type"] == "text/event-stream; charset=utf-8"
        assert "session=token" in http_response.headers["set-cookie"]

    def test_fluent_methods_clone_and_isolate_state(self) -> None:
        request = typing.cast(Request, Mock())
        builder = response(request)

        authenticated = builder.with_cookie("session", "token")
        logged_out = builder.with_delete_cookie("session")
        overridden = builder.clone(cookies={"override": "value"}, delete_cookies=("old",))

        assert authenticated is not builder
        assert logged_out is not builder
        assert overridden is not builder

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


class TestServerSentEvent:
    def test_encodes_a_data_only_event(self) -> None:
        event = ServerSentEvent(data="hello")

        assert event.encode() == b"data: hello\r\n\r\n"

    def test_encodes_every_field_in_specification_order(self) -> None:
        event = ServerSentEvent(data="payload", event="update", id="42", retry=3000, comment="note")

        assert event.encode() == b": note\r\nevent: update\r\nid: 42\r\nretry: 3000\r\ndata: payload\r\n\r\n"

    def test_splits_multiline_data_into_one_line_per_field(self) -> None:
        event = ServerSentEvent(data="first\nsecond\r\nthird\rfourth")

        assert event.encode() == b"data: first\r\ndata: second\r\ndata: third\r\ndata: fourth\r\n\r\n"

    def test_splits_a_multiline_comment(self) -> None:
        event = ServerSentEvent(comment="first\nsecond")

        assert event.encode() == b": first\r\n: second\r\n\r\n"

    def test_keeps_trailing_and_exotic_line_breaks_inside_data(self) -> None:
        # the client joins data lines with LF and strips one trailing LF, so a trailing newline
        # must survive the round trip; U+2028 and friends are payload, not line terminators
        assert ServerSentEvent(data="text\n").encode() == b"data: text\r\ndata: \r\n\r\n"
        assert ServerSentEvent(data="a\u2028b").encode() == "data: a\u2028b\r\n\r\n".encode()
        assert ServerSentEvent(data="a\x0bb").encode() == b"data: a\x0bb\r\n\r\n"

    def test_encodes_empty_data_as_a_single_empty_field(self) -> None:
        event = ServerSentEvent(data="")

        assert event.encode() == b"data: \r\n\r\n"

    def test_encodes_a_comment_only_frame(self) -> None:
        event = ServerSentEvent(comment="keepalive")

        assert event.encode() == b": keepalive\r\n\r\n"

    def test_encodes_data_with_a_custom_charset(self) -> None:
        event = ServerSentEvent(data="привет")

        assert event.encode("cp1251") == "data: привет\r\n\r\n".encode("cp1251")

    def test_rejects_frame_injection_via_metadata_fields(self) -> None:
        with pytest.raises(ValueError, match="'event' must not contain CR, LF or NUL"):
            ServerSentEvent(data="payload", event="update\ndata: forged")

        with pytest.raises(ValueError, match="'id' must not contain CR, LF or NUL"):
            ServerSentEvent(data="payload", id="1\r\nevent: forged")

        with pytest.raises(ValueError, match="'id' must not contain CR, LF or NUL"):
            ServerSentEvent(data="payload", id="1\x00")

    def test_rejects_a_negative_retry(self) -> None:
        with pytest.raises(ValueError, match="'retry' must not be negative"):
            ServerSentEvent(retry=-1)


class TestSSEResponse:
    async def test_streams_events_and_declares_streaming_headers(self, scope_f: ScopeFactory) -> None:
        async def events() -> typing.AsyncIterator[ServerSentEvent | str]:
            yield ServerSentEvent(data="first", event="update", id="1")
            yield "second"

        http_response = SSEResponse(events(), headers={"X-Test": "yes"}, keepalive_interval=None)
        messages: list[typing.Any] = []

        receive = typing.cast(Receive, Mock())

        async def send(message: typing.Any) -> None:
            messages.append(message)

        await http_response(scope_f(), receive, send)

        body = b"".join(message["body"] for message in messages if message["type"] == "http.response.body")
        assert http_response.status_code == 200
        assert http_response.headers["content-type"] == "text/event-stream; charset=utf-8"
        assert http_response.headers["cache-control"] == "no-store"
        assert http_response.headers["x-accel-buffering"] == "no"
        assert http_response.headers["x-test"] == "yes"
        assert "content-length" not in http_response.headers
        assert body == b"event: update\r\nid: 1\r\ndata: first\r\n\r\ndata: second\r\n\r\n"
        assert messages[-1] == {"type": "http.response.body", "body": b"", "more_body": False}

    async def test_streams_a_sync_iterable_of_events(self, scope_f: ScopeFactory) -> None:
        def events() -> typing.Iterator[ServerSentEvent]:
            yield ServerSentEvent(data="first")
            yield ServerSentEvent(data="second")

        http_response = SSEResponse(events(), keepalive_interval=None)
        messages: list[typing.Any] = []

        receive = typing.cast(Receive, Mock())

        async def send(message: typing.Any) -> None:
            messages.append(message)

        await http_response(scope_f(), receive, send)

        body = b"".join(message["body"] for message in messages if message["type"] == "http.response.body")
        assert body == b"data: first\r\n\r\ndata: second\r\n\r\n"

    def test_overrides_a_caller_supplied_cache_control(self) -> None:
        http_response = SSEResponse([], headers={"Cache-Control": "public, max-age=3600"}, keepalive_interval=None)

        assert http_response.headers["cache-control"] == "no-store"

    def test_rejects_a_non_positive_keepalive_interval(self) -> None:
        for interval in (0, -1.0):
            with pytest.raises(ValueError, match="keepalive interval must be positive"):
                SSEResponse([], keepalive_interval=interval)

    async def test_translates_a_client_disconnect(self, scope_f: ScopeFactory) -> None:
        async def events() -> typing.AsyncIterator[ServerSentEvent]:
            yield ServerSentEvent(data="first")

        http_response = SSEResponse(events(), keepalive_interval=None)
        receive = typing.cast(Receive, Mock())

        async def send(message: typing.Any) -> None:
            if message["type"] == "http.response.body":
                raise OSError("client went away")

        # Starlette maps OSError onto ClientDisconnect, which only works if the type survives
        with pytest.raises(ClientDisconnect):
            await http_response(scope_f(), receive, send)

    async def test_sends_keepalives_on_a_fixed_interval(self, scope_f: ScopeFactory) -> None:
        async def events() -> typing.AsyncIterator[ServerSentEvent]:
            await anyio.sleep(0.15)
            yield ServerSentEvent(data="late")

        http_response = SSEResponse(events(), keepalive_interval=0.01)
        messages: list[typing.Any] = []

        receive = typing.cast(Receive, Mock())

        async def send(message: typing.Any) -> None:
            messages.append(message)

        await http_response(scope_f(), receive, send)

        body = b"".join(message["body"] for message in messages if message["type"] == "http.response.body")
        assert body.count(b": keepalive\r\n\r\n") >= 1
        # a keepalive may still land between the event and the end of the stream
        assert b"data: late\r\n\r\n" in body

    async def test_propagates_a_failing_source_without_terminating_the_stream(self, scope_f: ScopeFactory) -> None:
        async def events() -> typing.AsyncIterator[ServerSentEvent]:
            yield ServerSentEvent(data="first")
            raise RuntimeError("boom")

        http_response = SSEResponse(events(), keepalive_interval=None)
        messages: list[typing.Any] = []

        receive = typing.cast(Receive, Mock())

        async def send(message: typing.Any) -> None:
            messages.append(message)

        # the cause keeps its own type: it must not arrive wrapped in an ExceptionGroup
        with pytest.raises(RuntimeError, match="boom"):
            await http_response(scope_f(), receive, send)

        body = b"".join(message["body"] for message in messages if message["type"] == "http.response.body")
        assert body == b"data: first\r\n\r\n"
        # the stream is left unterminated so the client sees a truncated response, not a clean end
        assert messages[-1]["more_body"] is True

    async def test_does_not_send_keepalives_when_disabled(self, scope_f: ScopeFactory) -> None:
        async def events() -> typing.AsyncIterator[ServerSentEvent]:
            await anyio.sleep(0.05)
            yield ServerSentEvent(data="late")

        http_response = SSEResponse(events(), keepalive_interval=None)
        messages: list[typing.Any] = []

        receive = typing.cast(Receive, Mock())

        async def send(message: typing.Any) -> None:
            messages.append(message)

        await http_response(scope_f(), receive, send)

        body = b"".join(message["body"] for message in messages if message["type"] == "http.response.body")
        assert body == b"data: late\r\n\r\n"
