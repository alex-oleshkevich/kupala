import dataclasses
import os
import typing
from urllib.parse import SplitResult, unquote, urlsplit, urlunsplit

import anyio
from anyio.streams.memory import MemoryObjectSendStream
from starlette.concurrency import iterate_in_threadpool
from starlette.datastructures import URL
from starlette.responses import (
    ContentStream,
    FileResponse,
    HTMLResponse,
    PlainTextResponse,
    RedirectResponse,
    Response,
    StreamingResponse,
)
from starlette.responses import (
    JSONResponse as BaseJSONResponse,
)
from starlette.types import Send

from kupala.requests import Request
from kupala.templates import RendersToResponse

__all__ = [
    "BackResponse",
    "ContentStream",
    "FileResponse",
    "HTMLResponse",
    "JSONResponse",
    "PlainTextResponse",
    "RedirectResponse",
    "Response",
    "ResponseBuilder",
    "SSEResponse",
    "ServerSentEvent",
    "ServerSentEventStream",
    "StreamingResponse",
    "response",
]

type ServerSentEventStream = typing.Iterable[ServerSentEvent | str] | typing.AsyncIterable[ServerSentEvent | str]


class HTMLLike(typing.Protocol):
    def __html__(self) -> str: ...


class ResponseBuilder:
    def __init__(self, request: Request) -> None:
        self._request = request
        self._cookies: dict[str, str] = {}
        self._delete_cookies: tuple[str, ...] = ()

    def clone(
        self,
        *,
        cookies: typing.Mapping[str, str] | None = None,
        delete_cookies: typing.Sequence[str] | None = None,
    ) -> typing.Self:
        clone = type(self)(self._request)
        clone._cookies = dict(self._cookies if cookies is None else cookies)
        clone._delete_cookies = tuple(self._delete_cookies if delete_cookies is None else delete_cookies)
        return clone

    def _apply_cookies(self, response: Response) -> Response:
        for key, value in self._cookies.items():
            response.set_cookie(key, value)
        for key in self._delete_cookies:
            response.delete_cookie(key)
        return response

    def template(
        self,
        template_name: str,
        context: typing.Mapping[str, typing.Any] | None = None,
        *,
        status_code: int = 200,
        headers: typing.Mapping[str, str] | None = None,
        media_type: str = "text/html",
    ) -> Response:
        renderer: RendersToResponse = self._request.state.template_renderer
        response = renderer.render_to_response(
            self._request,
            template_name,
            context,
            status_code=status_code,
            media_type=media_type,
            headers=headers,
        )
        return self._apply_cookies(response)

    def json(
        self,
        content: typing.Any,
        *,
        status_code: int = 200,
        headers: typing.Mapping[str, str] | None = None,
        media_type: str | None = None,
    ) -> Response:
        response = JSONResponse(content, status_code=status_code, headers=headers, media_type=media_type)
        return self._apply_cookies(response)

    def empty(self, *, headers: typing.Mapping[str, str] | None = None) -> Response:
        response = Response(status_code=204, headers=headers)
        return self._apply_cookies(response)

    def text(
        self,
        content: str,
        *,
        status_code: int = 200,
        headers: typing.Mapping[str, str] | None = None,
        media_type: str | None = None,
    ) -> Response:
        response = PlainTextResponse(content, status_code=status_code, headers=headers, media_type=media_type)
        return self._apply_cookies(response)

    def html(
        self,
        content: str | HTMLLike,
        *,
        status_code: int = 200,
        headers: typing.Mapping[str, str] | None = None,
        media_type: str | None = None,
    ) -> Response:
        if hasattr(content, "__html__"):
            content = content.__html__()

        response = HTMLResponse(content, status_code=status_code, headers=headers, media_type=media_type)
        return self._apply_cookies(response)

    def redirect(
        self,
        url: str | URL,
        *,
        status_code: int = 302,
        headers: typing.Mapping[str, str] | None = None,
    ) -> Response:
        response = RedirectResponse(url, status_code=status_code, headers=headers)
        return self._apply_cookies(response)

    def redirect_to(
        self,
        path_name: str,
        path_params: dict[str, typing.Any],
        *,
        status_code: int = 302,
        headers: typing.Mapping[str, str] | None = None,
    ) -> Response:
        url = self._request.url_for(path_name, **path_params)
        response = RedirectResponse(url, status_code=status_code, headers=headers)
        return self._apply_cookies(response)

    def back(
        self,
        *,
        status_code: typing.Literal[302, 303] = 303,
        headers: typing.Mapping[str, str] | None = None,
    ) -> Response:
        response = BackResponse(
            self._request,
            status_code=status_code,
            headers=headers,
        )
        return self._apply_cookies(response)

    def file(
        self,
        path: str | os.PathLike[str],
        *,
        status_code: int = 200,
        headers: typing.Mapping[str, str] | None = None,
        media_type: str | None = None,
        filename: str | None = None,
        stat_result: os.stat_result | None = None,
        content_disposition: typing.Literal["inline", "attachment"] = "attachment",
    ) -> Response:
        response = FileResponse(
            path,
            filename=filename,
            stat_result=stat_result,
            media_type=media_type,
            status_code=status_code,
            headers=headers,
            content_disposition_type=content_disposition,
        )
        return self._apply_cookies(response)

    def stream(
        self,
        content: ContentStream,
        *,
        status_code: int = 200,
        headers: typing.Mapping[str, str] | None = None,
        media_type: str | None = None,
    ) -> Response:
        response = StreamingResponse(
            content,
            headers=headers,
            status_code=status_code,
            media_type=media_type,
        )
        return self._apply_cookies(response)

    def sse(
        self,
        content: ServerSentEventStream,
        *,
        status_code: int = 200,
        headers: typing.Mapping[str, str] | None = None,
        keepalive_interval: float | None = 15.0,
    ) -> Response:
        response = SSEResponse(
            content,
            status_code=status_code,
            headers=headers,
            keepalive_interval=keepalive_interval,
        )
        return self._apply_cookies(response)

    def with_cookie(self, key: str, value: str) -> typing.Self:
        cookies = self._cookies.copy()
        cookies[key] = value
        return self.clone(cookies=cookies)

    def with_delete_cookie(self, key: str) -> typing.Self:
        return self.clone(delete_cookies=(*self._delete_cookies, key))


def response(request: Request) -> ResponseBuilder:
    return ResponseBuilder(request)


@dataclasses.dataclass(frozen=True, slots=True)
class ServerSentEvent:
    data: str | None = None
    event: str | None = None
    id: str | None = None
    retry: int | None = None
    comment: str | None = None

    LINE_SEPARATOR: typing.ClassVar[str] = "\r\n"
    FORBIDDEN_CHARS: typing.ClassVar[frozenset[str]] = frozenset({"\r", "\n", "\x00"})

    def __post_init__(self) -> None:
        for field_name, value in (("event", self.event), ("id", self.id)):
            if value is not None and self.FORBIDDEN_CHARS.intersection(value):
                raise ValueError(f"Server-sent event field {field_name!r} must not contain CR, LF or NUL.")

        if self.retry is not None and self.retry < 0:
            raise ValueError("Server-sent event field 'retry' must not be negative.")

    def encode(self, charset: str = "utf-8") -> bytes:
        lines: list[str] = []
        if self.comment is not None:
            lines.extend(self._field_lines(":", self.comment))
        if self.event is not None:
            lines.append(f"event: {self.event}")
        if self.id is not None:
            lines.append(f"id: {self.id}")
        if self.retry is not None:
            lines.append(f"retry: {self.retry}")
        if self.data is not None:
            lines.extend(self._field_lines("data:", self.data))

        frame = self.LINE_SEPARATOR.join([*lines, ""]) + self.LINE_SEPARATOR
        return frame.encode(charset)

    @staticmethod
    def _field_lines(prefix: str, value: str) -> typing.Iterator[str]:
        for line in value.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
            yield f"{prefix} {line}"


class SSEResponse(StreamingResponse):
    keepalive_event: typing.ClassVar[ServerSentEvent] = ServerSentEvent(comment="keepalive")

    def __init__(
        self,
        content: ServerSentEventStream,
        *,
        status_code: int = 200,
        headers: typing.Mapping[str, str] | None = None,
        keepalive_interval: float | None = 15.0,
    ) -> None:
        self.keepalive_interval = keepalive_interval
        super().__init__(
            self._encode_events(content),
            status_code=status_code,
            headers=headers,
            media_type="text/event-stream",
        )
        # buffering proxies defeat streaming, and a cached event stream is never correct
        self.headers["cache-control"] = "no-store"
        self.headers["x-accel-buffering"] = "no"

    async def _encode_events(self, content: ServerSentEventStream) -> typing.AsyncIterator[bytes]:
        events = content if isinstance(content, typing.AsyncIterable) else iterate_in_threadpool(content)
        async for event in events:
            frame = event if isinstance(event, ServerSentEvent) else ServerSentEvent(data=event)
            yield frame.encode(self.charset)

    async def _produce_events(self, stream: MemoryObjectSendStream[bytes | None]) -> None:
        async with stream:
            async for chunk in self.body_iterator:
                await stream.send(typing.cast(bytes, chunk))
            await stream.send(None)

    async def _produce_keepalives(self, stream: MemoryObjectSendStream[bytes | None], interval: float) -> None:
        frame = self.keepalive_event.encode(self.charset)
        async with stream:
            while True:
                await anyio.sleep(interval)
                await stream.send(frame)

    async def stream_response(self, send: Send) -> None:
        await send({"type": "http.response.start", "status": self.status_code, "headers": self.raw_headers})

        # a rendezvous stream merges events and keepalives; cancelling a pending `receive()` would drop
        # an already handed-off item, so the producer signals completion with a `None` sentinel
        send_stream, receive_stream = anyio.create_memory_object_stream[bytes | None](0)
        async with anyio.create_task_group() as task_group, receive_stream:
            if self.keepalive_interval is not None:
                task_group.start_soon(self._produce_keepalives, send_stream.clone(), self.keepalive_interval)
            task_group.start_soon(self._produce_events, send_stream)

            async for chunk in receive_stream:
                if chunk is None:
                    break
                await send({"type": "http.response.body", "body": chunk, "more_body": True})

            task_group.cancel_scope.cancel()

        await send({"type": "http.response.body", "body": b"", "more_body": False})


class JSONResponse(BaseJSONResponse): ...  # pragma: no branch


class BackResponse(RedirectResponse):
    _ORD_BOUND = 0x20
    _ORD_DEL = 0x7F

    def __init__(
        self,
        request: Request,
        *,
        status_code: typing.Literal[302, 303] = 303,
        headers: typing.Mapping[str, str] | None = None,
    ) -> None:
        if status_code not in {302, 303}:
            raise ValueError("back() only supports 302 or 303 redirects")

        response_headers = {key: value for key, value in (headers or {}).items() if key.lower() != "cache-control"}
        response_headers["cache-control"] = "no-store"
        super().__init__(
            self._safe_back_url(request),
            status_code=status_code,
            headers=response_headers,
        )

    @classmethod
    def _effective_port(cls, url: SplitResult) -> int:
        if url.port is not None:
            return url.port

        return {"http": 80, "https": 443}[url.scheme.lower()]

    @classmethod
    def _same_http_origin(cls, target: SplitResult, current: SplitResult) -> bool:
        try:
            if target.scheme.lower() not in {"http", "https"}:
                return False
            if target.scheme.lower() != current.scheme.lower():
                return False
            if target.username is not None or target.password is not None:
                return False

            return (
                target.hostname is not None
                and target.hostname == current.hostname
                and cls._effective_port(target) == cls._effective_port(current)
            )
        except ValueError:
            return False

    @classmethod
    def _safe_back_url(cls, request: Request) -> str:
        root_path = request.scope.get("root_path", "")
        if not isinstance(root_path, str) or not cls._is_safe_path(root_path, allow_empty=True):
            return "/"

        fallback = root_path or "/"
        root_boundary = root_path.rstrip("/") or "/"
        referer = request.headers.get("referer")
        if referer is None or "\\" in referer or any(cls._is_forbidden_char(char) for char in referer):
            return fallback

        try:
            target = urlsplit(referer)
            current = urlsplit(str(request.url))

            if target.scheme or target.netloc:
                if not cls._same_http_origin(target, current):
                    return fallback
            elif not referer.startswith("/") or referer.startswith("//"):
                return fallback

            path = target.path or "/"
            if not cls._is_safe_path(path) or not cls._is_within_root(path, root_boundary):
                return fallback

            return urlunsplit(("", "", path, target.query, target.fragment))
        except ValueError:
            return fallback

    @staticmethod
    def _is_within_root(path: str, root_path: str) -> bool:
        return root_path == "/" or path == root_path or path.startswith(f"{root_path}/")

    @classmethod
    def _is_safe_path(cls, path: str, *, allow_empty: bool = False) -> bool:
        if not path:
            return allow_empty
        if not path.startswith("/") or path.startswith("//") or "?" in path or "#" in path:
            return False

        decoded_path = unquote(path)
        if any(cls._is_forbidden_char(char) for char in decoded_path) or "\\" in decoded_path:
            return False

        return all(segment not in {".", ".."} for segment in decoded_path.split("/"))

    @classmethod
    def _is_forbidden_char(cls, char: str) -> bool:
        return ord(char) <= cls._ORD_BOUND or ord(char) == cls._ORD_DEL
