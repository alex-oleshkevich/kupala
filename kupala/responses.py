from __future__ import annotations

import typing
from starlette import responses
from starlette.background import BackgroundTask
from starlette.responses import FileResponse, HTMLResponse, PlainTextResponse, Response, StreamingResponse
from starlette_flash import flash

from kupala.json import dumps as json_dump
from kupala.requests import Request

__all__ = [
    "Response",
    "PlainTextResponse",
    "HTMLResponse",
    "EmptyResponse",
    "JSONResponse",
    "JSONErrorResponse",
    "FileResponse",
    "StreamingResponse",
    "RedirectResponse",
]


class EmptyResponse(responses.Response):
    def __init__(
        self,
        *,
        headers: typing.Mapping[str, str] | None = None,
        media_type: str | None = None,
        background: BackgroundTask | None = None,
    ) -> None:
        super().__init__(status_code=204, headers=headers, media_type=media_type, background=background)


class JSONResponse(responses.JSONResponse):
    def __init__(
        self,
        content: typing.Any,
        *,
        status_code: int = 200,
        indent: int | None = 4,
        headers: typing.Mapping[str, typing.Any] | None = None,
        media_type: str | None = None,
        json_default: typing.Callable[[typing.Any], typing.Any] | None = None,
        background: BackgroundTask | None = None,
    ) -> None:
        self.indent = indent
        self.json_default = json_default
        super().__init__(
            content=content,
            status_code=status_code,
            headers=headers,
            media_type=media_type,
            background=background,
        )

    def render(self, content: typing.Any) -> bytes:
        return json_dump(
            content,
            ensure_ascii=False,
            allow_nan=False,
            indent=self.indent,
            default=self.json_default,
            separators=(",", ":"),
        ).encode("utf-8")


class JSONErrorResponse(JSONResponse):
    def __init__(
        self,
        message: str,
        errors: typing.Mapping[str, list[str]] | None = None,
        *,
        error_code: str = "",
        status_code: int = 400,
        indent: int = 4,
        headers: typing.Mapping[str, typing.Any] | None = None,
        json_default: typing.Callable[[typing.Any], typing.Any] | None = None,
        background: BackgroundTask | None = None,
    ) -> None:
        errors = errors or {}
        super().__init__(
            {"message": message, "errors": errors, "code": error_code},
            status_code=status_code,
            headers=headers,
            indent=indent,
            json_default=json_default,
            background=background,
        )


class RedirectResponse(responses.RedirectResponse):
    @classmethod
    def to_url(
        cls,
        request: Request,
        url: str,
        flash_message: str,
        flash_category: str = "success",
        *,
        status_code: int = 302,
        headers: typing.Mapping[str, typing.Any] | None = None,
        background: BackgroundTask | None = None,
    ) -> RedirectResponse:
        flash(request).add(flash_message, flash_category)
        return cls(url, status_code=status_code, headers=headers, background=background)

    @classmethod
    def to_path_name(
        cls,
        request: Request,
        path_name: str,
        path_params: typing.Mapping[str, str | int | float] | None = None,
        *,
        status_code: int = 302,
        headers: typing.Mapping[str, typing.Any] | None = None,
        background: BackgroundTask | None = None,
        flash_message: str | None = None,
        flash_category: str = "success",
    ) -> RedirectResponse:
        path_params = path_params or {}
        url = request.url_for(path_name, **path_params)
        if flash_message:
            flash(request).add(flash_message, flash_category)
        return cls(url, status_code=status_code, headers=headers, background=background)

    @classmethod
    def back(
        cls,
        request: Request,
        *,
        flash_message: str | None = None,
        flash_category: str = "success",
        headers: typing.Mapping[str, typing.Any] | None = None,
        background: BackgroundTask | None = None,
    ) -> RedirectResponse:
        redirect_to = request.headers.get("referer", "/")
        current_origin = request.url.netloc
        if current_origin not in redirect_to:
            redirect_to = "/"

        if flash_message:
            flash(request).add(flash_message, flash_category)
        return cls(redirect_to, status_code=302, headers=headers, background=background)
