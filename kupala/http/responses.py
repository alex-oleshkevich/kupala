from __future__ import annotations

import inspect
import os
import typing
from starlette import responses
from starlette.responses import ContentStream
from starlette.types import Receive, Scope, Send
from urllib.parse import quote

from kupala import json as jsonlib
from kupala.http.middleware.flash_messages import FlashBag
from kupala.http.requests import Request
from kupala.json import JSONEncoder
from kupala.structures import Cookie

_T = typing.TypeVar("_T", bound="Response")


class Response:
    def __init__(
        self,
        content: typing.Any | None = None,
        *,
        status_code: int = 200,
        headers: typing.Mapping[str, typing.Any] | None = None,
        content_type: str | None = None,
    ) -> None:
        self.content = content
        self.headers = dict(headers or {})
        self.status_code = status_code
        self.content_type = content_type
        self._cookies: list[Cookie] = []
        self._cookie_to_delete: list[Cookie] = []

    def set_cookie(
        self: _T,
        name: str,
        value: str = "",
        max_age: int | None = None,
        expires: int | None = None,
        path: str = "/",
        domain: str | None = None,
        secure: bool = False,
        httponly: bool = False,
        samesite: typing.Literal["lax", "strict", "none"] | None = "lax",
    ) -> _T:
        self._cookies.append(
            Cookie(
                name=name,
                value=value,
                max_age=max_age,
                expires=expires,
                path=path,
                domain=domain,
                secure=secure,
                httponly=httponly,
                samesite=samesite,
            )
        )
        return self

    def delete_cookie(
        self: _T,
        name: str,
        path: str = "/",
        domain: str | None = None,
        secure: bool = False,
        httponly: bool = False,
        samesite: typing.Literal["lax", "strict", "none"] | None = "lax",
    ) -> _T:
        self._cookie_to_delete.append(
            Cookie(name=name, path=path, domain=domain, secure=secure, httponly=httponly, samesite=samesite)
        )
        return self

    def create_http_response(self, request: Request) -> responses.Response:
        return responses.Response(
            self.content,
            status_code=self.status_code,
            headers=self.headers,
            media_type=self.content_type,
        )

    def status(self: _T, code: int) -> _T:
        self.status_code = code
        return self

    def _process(self, http_response: responses.Response) -> None:
        self._process_cookies(http_response)

    def _process_cookies(self, http_response: responses.Response) -> None:
        # apply any pending cookie
        for cookie in self._cookies:
            http_response.set_cookie(
                key=cookie.name,
                value=cookie.value,
                max_age=cookie.max_age,
                expires=cookie.expires,
                path=cookie.path,
                domain=cookie.domain,
                secure=cookie.secure,
                httponly=cookie.httponly,
                samesite=cookie.samesite,
            )

        # delete cookies
        for cookie in self._cookie_to_delete:
            http_response.delete_cookie(
                key=cookie.name,
                path=cookie.path,
                domain=cookie.domain,
                secure=cookie.secure,
                httponly=cookie.httponly,
                samesite=cookie.samesite,
            )

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        request = Request(scope, receive, send)
        response = self.create_http_response(request)
        self._process(response)
        await response(scope, receive, send)

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}: status_code={self.status_code}>"


class TemplateResponse(Response):
    def __init__(
        self,
        template_name: str,
        context: typing.Mapping[str, typing.Any] | None = None,
        *,
        status_code: int = 200,
        headers: typing.Mapping[str, typing.Any] | None = None,
        content_type: str = "text/html",
    ) -> None:
        super().__init__(status_code=status_code, headers=headers, content_type=content_type)
        self.template_name = template_name
        self.context = dict(context or {})

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        request = Request(scope, receive, send)
        for processor in request.app.get_template_context_processors():
            if inspect.iscoroutinefunction(processor):
                self.context.update(await processor(request))  # type: ignore[misc]
            else:
                self.context.update(processor(request))  # type: ignore[arg-type]

        self.context.update(
            {
                "app": request.app,
                "request": request,
                "url": request.url_for,
                "static": request.app.static_url,
            }
        )
        self.content = request.app.render(self.template_name, self.context).encode("utf-8")
        await super().__call__(scope, receive, send)


template = TemplateResponse


class BaseTextResponse(Response):
    content_type: str = ""

    def __init__(
        self,
        content: str,
        *,
        status_code: int = 200,
        headers: typing.Mapping[str, typing.Any] | None = None,
    ) -> None:
        super().__init__(status_code=status_code, headers=headers, content_type=self.content_type)
        self.content = content


class PlainTextResponse(BaseTextResponse):
    content_type = "text/plain"


text = PlainTextResponse


class HTMLResponse(BaseTextResponse):
    content_type = "text/html"


html = HTMLResponse


class JSONResponse(Response):
    content_type = "application/json"

    def __init__(
        self,
        data: typing.Any,
        *,
        status_code: int = 200,
        indent: int = 4,
        headers: typing.Mapping[str, typing.Any] | None = None,
        encoder_class: typing.Type[JSONEncoder] | None = None,
        default: typing.Callable[[typing.Any], typing.Any] | None = None,
    ) -> None:
        super().__init__(status_code=status_code, headers=headers, content_type=self.content_type)
        self.data = data
        self.indent = indent
        self.default = default
        self.encoder_class = encoder_class
        if not encoder_class:
            self.default = default or jsonlib.json_default

    def create_http_response(self, request: Request) -> responses.Response:
        self.content = jsonlib.dumps(
            jsonlib.jsonify(self.data),
            ensure_ascii=False,
            allow_nan=False,
            indent=self.indent,
            default=None if self.encoder_class else self.default,
            cls=self.encoder_class,
            separators=(",", ":"),
        ).encode("utf-8")
        return super().create_http_response(request)


json = JSONResponse


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
        encoder_class: typing.Type[JSONEncoder] | None = None,
        default: typing.Callable[[typing.Any], typing.Any] | None = None,
    ) -> None:
        errors = errors or {}
        super().__init__(
            {"message": message, "errors": errors, "code": error_code},
            status_code=status_code,
            headers=headers,
            indent=indent,
            default=default,
            encoder_class=encoder_class,
        )


json_error = JSONErrorResponse


class FileResponse(Response):
    def __init__(
        self,
        path: str | os.PathLike[str],
        *,
        status_code: int = 200,
        file_name: str | None = None,
        inline: bool = False,
        headers: typing.Mapping[str, typing.Any] | None = None,
        content_type: str | None = None,  # guess type
    ) -> None:
        super().__init__(status_code=status_code, headers=headers, content_type=content_type)
        self.path = path
        self.file_name = file_name
        self.content_disposition_type = "inline" if inline else "attachment"

    def create_http_response(self, request: Request) -> responses.Response:
        file_name = self.file_name or os.path.basename(self.path)
        file_name = quote(file_name, safe="")
        stat_result: os.stat_result | None = None
        if os.path.exists(self.path):
            stat_result = os.stat(self.path)

        return responses.FileResponse(
            path=self.path,
            status_code=self.status_code,
            headers=self.headers,
            media_type=self.content_type,
            filename=file_name,
            stat_result=stat_result,
            method=request.method,
            content_disposition_type=self.content_disposition_type,
        )


send_file = FileResponse


class StreamingResponse(Response):
    def __init__(
        self,
        content: ContentStream,
        *,
        status_code: int = 200,
        file_name: str | None = None,
        inline: bool = False,
        headers: typing.Mapping[str, typing.Any] | None = None,
        content_type: str = "application/octet-stream",
    ) -> None:
        super().__init__(status_code=status_code, headers=headers, content_type=content_type)
        self.streaming_content = content
        self.file_name = quote(file_name) if file_name else None
        disposition = "inline" if inline else "attachment"

        if file_name and disposition:
            self.headers.update({"content-disposition": f'{disposition}; filename="{file_name}"'})
        elif disposition:
            self.headers.update({"content-disposition": f"{disposition}"})

    def create_http_response(self, request: Request) -> responses.Response:
        return responses.StreamingResponse(
            content=self.streaming_content,
            status_code=self.status_code,
            headers=self.headers,
            media_type=self.content_type,
        )


stream = StreamingResponse


class RedirectResponse(Response):
    def __init__(
        self,
        url: str | None = None,
        *,
        status_code: int = 302,
        path_name: str | None = None,
        path_params: typing.Mapping[str, typing.Any] | None = None,
        flash_message: str | None = None,
        flash_category: str = "success",
        headers: typing.Mapping[str, typing.Any] | None = None,
        content_type: str = "application/octet-stream",
    ) -> None:
        super().__init__(status_code=status_code, headers=headers, content_type=content_type)
        self.url = url
        self.path_name = path_name
        self.path_params = path_params or {}
        self.flash_message = flash_message
        self.flash_category = flash_category

    def flash(self, message: str, category: str = "success") -> RedirectResponse:
        """Set a flash message to the response."""
        self.flash_message = message
        self.flash_category = category
        return self

    def with_error(self, message: str) -> RedirectResponse:
        return self.flash(message, category="error")

    def with_success(self, message: str) -> RedirectResponse:
        return self.flash(message, category="success")

    def to_path_name(
        self, path_name: str, path_params: typing.Mapping[str, typing.Any] | None = None
    ) -> RedirectResponse:
        self.path_name = path_name
        self.path_params = path_params or {}
        return self

    def create_http_response(self, request: Request) -> responses.Response:
        assert self.url or self.path_name, 'Either "url" or "path_name" argument must be passed.'

        if self.flash_message and "flash_messages" in request.scope:
            flashes = typing.cast(FlashBag, request.scope["flash_messages"])
            flashes.add(self.flash_message, self.flash_category)

        url = typing.cast(str, request.url_for(self.path_name, **self.path_params) if self.path_name else self.url)
        return responses.RedirectResponse(url=url, status_code=self.status_code, headers=self.headers)


redirect = RedirectResponse


class EmptyResponse(Response):
    def __init__(
        self,
        *,
        headers: typing.Mapping[str, typing.Any] | None = None,
        content_type: str = "application/octet-stream",
    ) -> None:
        super().__init__(content=b"", status_code=204, headers=headers, content_type=content_type)


empty = EmptyResponse


class GoBackResponse(Response):
    def __init__(
        self,
        *,
        flash_message: str | None = None,
        flash_category: str = "success",
        headers: typing.Mapping[str, typing.Any] | None = None,
    ) -> None:
        self.flash_message = flash_message
        self.flash_category = flash_category
        super().__init__(status_code=302, headers=headers)

    def flash(self, message: str, category: str = "success") -> GoBackResponse:
        """Set a flash message to the response."""
        self.flash_message = message
        self.flash_category = category
        return self

    def with_error(self, message: str) -> GoBackResponse:
        return self.flash(message, category="error")

    def with_success(self, message: str) -> GoBackResponse:
        return self.flash(message, category="success")

    def create_http_response(self, request: Request) -> responses.Response:
        redirect_to = request.headers.get("referer", "/")
        current_origin = request.url.netloc
        if current_origin not in redirect_to:
            redirect_to = "/"
        return responses.RedirectResponse(url=redirect_to, status_code=self.status_code, headers=self.headers)


back = GoBackResponse
