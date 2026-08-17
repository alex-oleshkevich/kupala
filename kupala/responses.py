import os
import typing
from urllib.parse import SplitResult, unquote, urlsplit, urlunsplit

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

from kupala.requests import Request
from kupala.templates import RendersToResponse

__all__ = ["BackResponse", "Response", "response"]


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
        text: str,
        *,
        status_code: int = 200,
        headers: typing.Mapping[str, str] | None = None,
        media_type: str | None = None,
    ) -> Response:
        response = PlainTextResponse(text, status_code=status_code, headers=headers, media_type=media_type)
        return self._apply_cookies(response)

    def html(
        self,
        *,
        status_code: int = 200,
        headers: typing.Mapping[str, str] | None = None,
        media_type: str | None = None,
    ) -> Response:
        response = HTMLResponse(status_code=status_code, headers=headers, media_type=media_type)
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
        headers = dict(headers or {})
        if content_disposition is not None:
            file_name = os.path.basename(filename or "data.bin")
            headers.setdefault(
                "content-disposition",
                f'{content_disposition}; filename="{file_name}"',
            )

        response = FileResponse(
            path,
            filename=filename,
            stat_result=stat_result,
            media_type=media_type,
            status_code=status_code,
            headers=headers,
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
        *,
        status_code: int = 200,
        headers: typing.Mapping[str, str] | None = None,
    ) -> Response:
        response = SSEResponse(status_code=status_code, headers=headers)
        return self._apply_cookies(response)

    def with_flash(self, message: str, category: str) -> typing.Self:
        return self.clone()

    def with_cookie(self, key: str, value: str) -> typing.Self:
        cookies = self._cookies.copy()
        cookies[key] = value
        return self.clone(cookies=cookies)

    def with_vary(self) -> typing.Self:
        return self.clone()

    def with_cache(self) -> typing.Self:
        return self.clone()

    def with_delete_cookie(self, key: str) -> typing.Self:
        return self.clone(delete_cookies=(*self._delete_cookies, key))

    def with_signed_cookie(self) -> typing.Self:
        return self.clone()

    def with_encrypted_cookie(self) -> typing.Self:
        return self.clone()


def response(request: Request) -> ResponseBuilder:
    return ResponseBuilder(request)


class SSEResponse(Response): ...


class JSONResponse(BaseJSONResponse): ...


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
