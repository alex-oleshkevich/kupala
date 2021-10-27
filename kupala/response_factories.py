import typing as t
from json import JSONEncoder
from pathlib import Path

from .requests import Request
from .responses import (
    EmptyResponse,
    FileResponse,
    HTMLResponse,
    JSONResponse,
    PlainTextResponse,
    RedirectResponse,
    StreamingResponse,
)


class ResponseFactory:
    def __init__(self, request: Request, status_code: int = 200, headers: dict = None) -> None:
        self.request = request
        self.status_code = status_code
        self.headers = headers

    def json(
        self,
        data: dict,
        default: t.Callable[[t.Any], t.Any] = None,
        indent: int = None,
        encoder_class: t.Type[JSONEncoder] = None,
    ) -> JSONResponse:
        return JSONResponse(
            data,
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
        content: t.Any,
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
        url: str = None,
        status_code: int = 302,
        *,
        input_data: t.Any = None,
        flash_message: str = None,
        flash_type: str = "info",
        path_name: str = None,
        path_params: dict = None,
    ) -> RedirectResponse:
        return RedirectResponse(
            url=url,
            status_code=status_code,
            headers=self.headers,
            input_data=input_data,
            flash_message=flash_message,
            flash_type=flash_type,
            path_name=path_name,
            path_params=path_params,
            request=self.request,
        )

    def back(
        self, input_data: t.Any = None, status_code: int = 302, flash_message: str = None, flash_type: str = "info"
    ) -> RedirectResponse:
        redirect_to = self.request.headers.get('referer', '/')
        current_origin = self.request.url.netloc
        if current_origin not in redirect_to:
            redirect_to = '/'
        return self.redirect(
            url=redirect_to,
            status_code=status_code,
            input_data=input_data,
            flash_message=flash_message,
            flash_type=flash_type,
        )

    def send_file(
        self,
        path: t.Union[str, Path],
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
