from __future__ import annotations

import typing
from starlette import responses
from starlette.background import BackgroundTask
from starlette.datastructures import URL
from starlette.requests import Request
from starlette.responses import RedirectResponse, Response

from kupala.json import dumps as json_dump, json_default as base_json_default

__all__ = [
    "redirect",
    "redirect_to_path",
    "redirect_back",
    "empty_response",
    "JSONResponse",
    "JSONErrorResponse",
]


def redirect(
    url: str | URL,
    *,
    query_params: dict[str, str | int] | None = None,
    status_code: int = 302,
    headers: typing.Mapping[str, str] | None = None,
    background: BackgroundTask | None = None,
) -> RedirectResponse:
    redirect_url = URL(str(url))
    redirect_url = redirect_url.include_query_params(**(query_params or {}))
    return RedirectResponse(redirect_url, status_code=status_code, headers=headers, background=background)


def redirect_to_path(
    request: Request,
    path_name: str,
    path_params: typing.Mapping[str, str | int] | None = None,
    *,
    query_params: dict[str, str | int] | None = None,
    status_code: int = 302,
    headers: typing.Mapping[str, str] | None = None,
    background: BackgroundTask | None = None,
) -> RedirectResponse:
    redirect_url = request.url_for(path_name, **(path_params or {}))
    redirect_url = redirect_url.include_query_params(**(query_params or {}))
    return RedirectResponse(str(redirect_url), status_code=status_code, headers=headers, background=background)


def redirect_back(
    request: Request,
    *,
    status_code: int = 302,
    background: BackgroundTask | None = None,
    headers: typing.Mapping[str, str] | None = None,
) -> RedirectResponse:
    referer = request.headers.get("referer", "/")
    if not request.url.hostname or request.url.hostname not in referer:
        referer = "/"
    return RedirectResponse(referer, status_code=status_code, background=background, headers=headers)


def empty_response(
    background: BackgroundTask | None = None,
    headers: typing.Mapping[str, str] | None = None,
) -> Response:
    return Response(status_code=204, background=background, headers=headers)


class JSONResponse(responses.JSONResponse):
    def __init__(
        self,
        content: typing.Any,
        *,
        status_code: int = 200,
        indent: int | None = 4,
        headers: typing.Dict[str, str] | None = None,
        media_type: str | None = None,
        json_default: typing.Callable[[typing.Any], typing.Any] = base_json_default,
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
        headers: typing.Dict[str, str] | None = None,
        json_default: typing.Callable[[typing.Any], typing.Any] = base_json_default,
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
