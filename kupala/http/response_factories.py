import typing
from json import JSONEncoder
from pathlib import Path

from kupala.http.requests import Request
from kupala.templating import TemplateResponse

from .responses import (
    EmptyResponse,
    FileResponse,
    GoBackResponse,
    HTMLResponse,
    JSONErrorResponse,
    JSONResponse,
    PlainTextResponse,
    RedirectResponse,
    StreamingResponse,
)


class ResponseFactory:
    def __init__(self, request: Request, status_code: int = 200, headers: dict | None = None) -> None:
        self.request = request
        self.status_code = status_code
        self.headers = headers

    def json(
        self,
        data: typing.Any,
        default: typing.Callable[[typing.Any], typing.Any] | None = None,
        indent: int = 4,
        encoder_class: typing.Type[JSONEncoder] | None = None,
    ) -> JSONResponse:
        return JSONResponse(
            data,
            status_code=self.status_code,
            headers=self.headers,
            default=default,
            indent=indent,
            encoder_class=encoder_class,
        )

    def json_error(
        self,
        message: str,
        errors: dict[str, list[str]] | None = None,
        code: str = '',
        default: typing.Callable[[typing.Any], typing.Any] | None = None,
        indent: int = 4,
        encoder_class: typing.Type[JSONEncoder] | None = None,
    ) -> JSONResponse:
        return JSONErrorResponse(
            message=message,
            errors=errors,
            code=code,
            status_code=self.status_code,
            headers=self.headers,
            default=default,
            indent=indent,
            encoder_class=encoder_class,
        )

    def text(self, content: str) -> PlainTextResponse:
        return PlainTextResponse(content, status_code=self.status_code, headers=self.headers)

    def html(self, content: str) -> HTMLResponse:
        return HTMLResponse(content, status_code=self.status_code, headers=self.headers)

    def stream(
        self,
        content: typing.Any,
        file_name: str = 'data.bin',
        content_type: str = 'application/octet-stream',
        inline: bool = False,
    ) -> StreamingResponse:
        return StreamingResponse(
            content=content,
            status_code=self.status_code,
            headers=self.headers,
            file_name=file_name,
            inline=inline,
            media_type=content_type,
        )

    def redirect(
        self,
        url: str | None = None,
        status_code: int = 302,
        *,
        flash_message: str | None = None,
        flash_category: str = "info",
        path_name: str | None = None,
        path_params: dict | None = None,
    ) -> RedirectResponse:
        return RedirectResponse(
            url=url,
            status_code=status_code,
            headers=self.headers,
            flash_message=flash_message,
            flash_category=flash_category,
            path_name=path_name,
            path_params=path_params,
        )

    def back(
        self,
        status_code: int = 302,
        flash_message: str | None = None,
        flash_category: str = "info",
    ) -> RedirectResponse:
        return GoBackResponse(
            request=self.request,
            flash_message=flash_message,
            flash_category=flash_category,
            status_code=status_code,
        )

    def send_file(
        self,
        path: str | Path,
        file_name: str,
        content_type: str = 'application/octet-stream',
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

    def empty(self) -> EmptyResponse:
        return EmptyResponse(headers=self.headers)

    def template(
        self, template_name: str, context: dict | None = None, media_type: str = 'text/html'
    ) -> TemplateResponse:
        return TemplateResponse(
            template_name=template_name,
            context=context,
            status_code=self.status_code,
            headers=self.headers,
            media_type=media_type,
        )


def response(request: Request, status_code: int = 200, headers: dict | None = None) -> ResponseFactory:
    return ResponseFactory(request, status_code, headers)
