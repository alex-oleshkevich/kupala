from __future__ import annotations

import os
import typing as t
import urllib.parse
from starlette import responses
from starlette.background import BackgroundTask
from starlette.datastructures import UploadFile
from starlette.types import Receive, Scope, Send
from urllib.parse import quote

from kupala import json
from kupala.constants import REDIRECT_INPUT_DATA_SESSION_KEY
from kupala.json import JSONEncoder
from kupala.requests import Request

Response = responses.Response
PlainTextResponse = responses.PlainTextResponse
HTMLResponse = responses.HTMLResponse


class JSONResponse(responses.JSONResponse):
    def __init__(
        self,
        content: t.Any,
        status_code: int = 200,
        headers: dict = None,
        indent: int = None,
        default: t.Callable[[t.Any], t.Any] = None,
        encoder_class: t.Type[JSONEncoder] = None,
    ):
        self._indent = indent
        self._encoder_class = encoder_class
        if not encoder_class:
            self._default = default or json.json_default

        super().__init__(content, status_code, headers)

    def render(self, content: t.Any) -> bytes:
        return json.dumps(
            json.jsonify(content),
            ensure_ascii=False,
            allow_nan=False,
            indent=self._indent,
            default=None if self._encoder_class else self._default,
            cls=self._encoder_class,
            separators=(",", ":"),
        ).encode("utf-8")


class FileResponse(responses.FileResponse):
    def __init__(
        self,
        path: t.Union[str, os.PathLike[str]],
        status_code: int = 200,
        headers: dict = None,
        media_type: str = None,
        file_name: str = None,
        inline: bool = False,
    ):
        headers = headers or {}
        file_name = file_name or os.path.basename(path)
        encoded = urllib.parse.quote_plus(file_name)
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
            headers.update({"content-disposition": f'{disposition}; filename="{file_name}"'})
        super().__init__(
            content=content,
            status_code=status_code,
            headers=headers,
            media_type=media_type,
        )


class RedirectResponse(responses.RedirectResponse):
    def __init__(
        self,
        url: str = None,
        status_code: int = 302,
        headers: dict = None,
        *,
        input_data: t.Mapping = None,
        flash_message: str = None,
        flash_category: str = "info",
        path_name: str = None,
        path_params: dict = None,
    ):
        self.status_code = status_code
        self.body = b''
        self.background: t.Optional[BackgroundTask] = None
        self.init_headers(headers)

        self._url = url
        self._flash_message = flash_message
        self._flash_message_category = flash_category
        self._input_data = input_data
        self._path_name = path_name
        self._path_params = path_params

        assert url or path_name, 'Either "url" or "path_name" argument must be passed.'

    def flash(self, message: str, category: str = 'success') -> RedirectResponse:
        """Set a flash message to the response."""
        self._flash_message = message
        self._flash_message_category = category
        return self

    def with_input(self, input_data: t.Mapping) -> RedirectResponse:
        """Redirect with form input data. Uploaded files will be removed from data."""
        self._input_data = {k: v for k, v in input_data.items() if not isinstance(v, UploadFile)}
        return self

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if self._flash_message and 'flash_messages' in scope:
            scope['flash_messages'].add(self._flash_message, self._flash_message_category)

        if self._input_data and 'session' in scope:
            scope['session'][REDIRECT_INPUT_DATA_SESSION_KEY] = self._input_data

        if self._path_name:
            url = scope['request'].url_for(self._path_name, **(self._path_params or {}))
        else:
            url = self._url

        self.headers["location"] = quote(str(url), safe=":/%#?=@[]!$&'()*+,;")

        return await super().__call__(scope, receive, send)


class EmptyResponse(responses.Response):
    def __init__(self, headers: dict = None) -> None:
        super().__init__(b'', status_code=204, headers=headers)


class GoBackResponse(RedirectResponse):
    def __init__(
        self,
        request: Request,
        flash_message: str = None,
        flash_category: str = 'info',
        input_data: t.Any = None,
        status_code: int = 302,
    ) -> None:
        redirect_to = request.headers.get('referer', '/')
        current_origin = request.url.netloc
        if current_origin not in redirect_to:
            redirect_to = '/'
        super().__init__(
            redirect_to,
            status_code=status_code,
            input_data=input_data,
            flash_message=flash_message,
            flash_category=flash_category,
        )
