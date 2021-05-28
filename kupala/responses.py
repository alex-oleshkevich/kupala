import os
import typing as t
from pathlib import Path
from urllib.parse import quote_plus

from starlette import responses
from starlette.background import BackgroundTask
from starlette.types import Receive, Scope, Send

from . import json
from .contracts import TemplateRenderer, URLResolver
from .requests import Request


class Response(responses.Response):
    ...


class TextResponse(responses.PlainTextResponse, Response):
    ...


class HTMLResponse(responses.HTMLResponse):
    ...


class FileResponse(responses.FileResponse):
    def __init__(
        self,
        path: t.Union[str, Path],
        status_code: int = 200,
        headers: dict = None,
        media_type: str = None,
        file_name: str = None,
        inline: bool = False,
    ):
        headers = headers or {}
        file_name = file_name or os.path.basename(path)
        encoded = quote_plus(file_name)
        disposition = "inline" if inline else "attachment"
        headers["Content-Disposition"] = f'{disposition}; filename="{encoded}"'
        super().__init__(
            path,
            status_code,
            headers,
            media_type=media_type,
        )


class StreamingResponse(responses.StreamingResponse):
    def __init__(
        self,
        content: t.Any,
        status_code: int = 200,
        headers: dict = None,
        media_type: str = None,
        file_name: str = None,
        inline: bool = False,
    ):
        disposition = "inline" if inline else "attachment"
        headers = headers or {}
        if file_name:
            headers.update(
                {"content-disposition": f'{disposition}; filename="{file_name}"'}
            )
        super().__init__(
            content=content,
            status_code=status_code,
            headers=headers,
            media_type=media_type,
        )


class RedirectResponse(responses.RedirectResponse):
    def __init__(
        self,
        request: Request,
        url: str,
        status_code: int = 302,
        headers: dict = None,
        data: t.Any = None,
    ):
        if "session" in request.scope and data:
            request.session["_redirect_data"] = data

        if not url.startswith("/") and not url.startswith("http"):
            url = request.app.get(URLResolver).resolve(url)

        super().__init__(url, status_code, headers)


class JSONResponse(responses.Response):
    def __init__(
        self,
        content: t.Any,
        status_code: int = 200,
        headers: dict = None,
        indent: int = None,
        default: t.Callable = None,
        encoder_class: t.Type[json.JSONEncoder] = None,
        allow_nan: bool = True,
    ):
        content = json.dumps(
            content,
            cls=encoder_class,
            default=default,
            indent=indent,
            allow_nan=allow_nan,
        )
        super().__init__(content, status_code, headers, "application/json")


class TemplateResponse(Response):
    """A template response.

    This response renders a template using a configured renderer."""

    media_type = "text/html"

    def __init__(
        self,
        request: Request,
        template: str,
        context: dict = None,
        status_code: int = 200,
        headers: dict = None,
        media_type: str = None,
        background: BackgroundTask = None,
    ):
        self.request = request
        self.renderer = request.app.get(TemplateRenderer)
        self.template = template
        self.context = context or {}
        if "request" not in self.context:
            self.context["request"] = request

        content = self.renderer.render(template, self.context)
        super().__init__(content, status_code, headers, media_type, background)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        extensions = self.request.get("extensions", {})
        if "http.response.template" in extensions:
            await send(
                {
                    "type": "http.response.template",
                    "template": self.template,
                    "context": self.context,
                }
            )
        await super().__call__(scope, receive, send)


class ResponseFactory:
    def __init__(
        self, request: "Request", status_code: int = 200, headers: dict = None
    ) -> None:
        self.request = request
        self.status_code = status_code
        self.headers = headers

    def template(self, template_name: str, context: dict = None) -> TemplateResponse:
        return TemplateResponse(
            self.request,
            template_name,
            context,
            status_code=self.status_code,
            headers=self.headers,
        )

    def json(
        self,
        data: dict,
        default: t.Callable = None,
        indent: int = None,
        encoder_class: t.Type[json.JSONEncoder] = None,
    ) -> JSONResponse:
        return JSONResponse(
            data,
            status_code=self.status_code,
            headers=self.headers,
            default=default,
            indent=indent,
            encoder_class=encoder_class,
        )

    def text(self, content: str) -> TextResponse:
        return TextResponse(
            content,
            status_code=self.status_code,
            headers=self.headers,
        )

    def html(self, content: str) -> HTMLResponse:
        return HTMLResponse(
            content,
            status_code=self.status_code,
            headers=self.headers,
        )

    def stream(
        self,
        content: t.Any,
        file_name: str = "data.bin",
        media_type: str = "application/octet-stream",
        inline: bool = False,
    ) -> StreamingResponse:
        return StreamingResponse(
            content=content,
            status_code=self.status_code,
            headers=self.headers,
            file_name=file_name,
            inline=inline,
            media_type=media_type,
        )

    def redirect(
        self,
        url: str,
        data: t.Any = None,
        status_code: int = 302,
    ) -> RedirectResponse:
        return RedirectResponse(
            self.request,
            url=url,
            status_code=status_code or self.status_code,
            headers=self.headers,
            data=data,
        )

    def back(
        self,
        data: t.Any = None,
        status_code: int = 302,
    ) -> RedirectResponse:
        redirect_to = self.request.headers.get("referer", "/")
        current_origin = self.request.url.netloc
        if current_origin not in redirect_to:
            redirect_to = "/"
        return self.redirect(
            url=redirect_to,
            status_code=status_code,
            data=data,
        )

    def send_file(
        self,
        path: t.Union[str, Path],
        file_name: str,
        content_type: str = "application/octet-stream",
        inline: bool = False,
    ) -> FileResponse:
        return FileResponse(
            path=path,
            status_code=self.status_code,
            headers=self.headers,
            media_type=content_type,
            file_name=file_name,
            inline=inline,
        )


def response(
    request: Request,
    status_code: int = 200,
    headers: dict = None,
) -> ResponseFactory:
    return ResponseFactory(request, status_code, headers)
