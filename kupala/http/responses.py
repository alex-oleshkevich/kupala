from __future__ import annotations

import os
import typing
import urllib.parse
from starlette import responses
from starlette.background import BackgroundTask
from starlette.types import Receive, Scope, Send
from urllib.parse import quote

from kupala import json
from kupala.http.requests import Request
from kupala.json import JSONEncoder


class Response(responses.Response):
    pass


class PlainTextResponse(Response, responses.PlainTextResponse):
    pass


class HTMLResponse(Response, responses.HTMLResponse):
    pass


class JSONResponse(Response, responses.JSONResponse):
    def __init__(
        self,
        content: typing.Any,
        status_code: int = 200,
        headers: dict | None = None,
        indent: int = 4,
        default: typing.Callable[[typing.Any], typing.Any] | None = None,
        encoder_class: typing.Type[JSONEncoder] | None = None,
    ):
        self._indent = indent
        self._encoder_class = encoder_class
        if not encoder_class:
            self._default = default or json.json_default

        super().__init__(content, status_code, headers)

    def render(self, content: typing.Any) -> bytes:
        return json.dumps(
            json.jsonify(content),
            ensure_ascii=False,
            allow_nan=False,
            indent=self._indent,
            default=None if self._encoder_class else self._default,
            cls=self._encoder_class,
            separators=(",", ":"),
        ).encode("utf-8")


class FileResponse(Response, responses.FileResponse):
    def __init__(
        self,
        path: str | os.PathLike[str],
        status_code: int = 200,
        headers: dict | None = None,
        media_type: str | None = None,
        file_name: str | None = None,
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

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        try:
            await super().__call__(scope, receive, send)
        except (FileNotFoundError, RuntimeError):
            response = Response('Not Found', status_code=404)
            await response(scope, receive, send)


class StreamingResponse(Response, responses.StreamingResponse):
    def __init__(
        self,
        content: typing.Any,
        status_code: int = 200,
        headers: dict | None = None,
        media_type: str | None = None,
        file_name: str | None = None,
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


RT = typing.TypeVar('RT', bound='RedirectResponse')


class RedirectResponse(Response, responses.RedirectResponse):
    def __init__(
        self,
        url: str | None = None,
        status_code: int = 302,
        headers: dict | None = None,
        *,
        flash_message: str | None = None,
        flash_category: str = "info",
        path_name: str | None = None,
        path_params: dict | None = None,
    ):
        self.status_code = status_code
        self.body = b''
        self.background: BackgroundTask | None = None
        self.init_headers(headers)

        self._url = url
        self._flash_message = flash_message
        self._flash_message_category = flash_category
        self._path_name = path_name
        self._path_params = path_params

        assert url or path_name, 'Either "url" or "path_name" argument must be passed.'

    def flash(self: RT, message: str, category: str = 'success') -> RT:
        """Set a flash message to the response."""
        self._flash_message = message
        self._flash_message_category = category
        return self

    def with_error(self: RT, message: str) -> RT:
        return self.flash(message, category='error')

    def with_success(self: RT, message: str) -> RT:
        return self.flash(message, category='success')

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if self._flash_message and 'flash_messages' in scope:
            scope['flash_messages'].add(self._flash_message, self._flash_message_category)

        if self._path_name:
            url = scope['request'].url_for(self._path_name, **(self._path_params or {}))
        else:
            url = self._url

        self.headers["location"] = quote(str(url), safe=":/%#?=@[]!$&'()*+,;")

        return await super().__call__(scope, receive, send)


class EmptyResponse(Response):
    def __init__(self, headers: dict | None = None) -> None:
        super().__init__(b'', status_code=204, headers=headers)


class GoBackResponse(RedirectResponse):
    def __init__(
        self,
        request: Request,
        flash_message: str | None = None,
        flash_category: str = 'info',
        status_code: int = 302,
    ) -> None:
        redirect_to = request.headers.get('referer', '/')
        current_origin = request.url.netloc
        if current_origin not in redirect_to:
            redirect_to = '/'
        super().__init__(
            redirect_to,
            status_code=status_code,
            flash_message=flash_message,
            flash_category=flash_category,
        )


class JSONErrorResponse(JSONResponse):
    def __init__(
        self,
        message: str,
        errors: dict[str, list[str]] | None = None,
        code: str = '',
        status_code: int = 200,
        headers: dict | None = None,
        indent: int = 4,
        default: typing.Callable[[typing.Any], typing.Any] | None = None,
        encoder_class: typing.Type[JSONEncoder] | None = None,
    ) -> None:
        errors = errors or {}
        super().__init__(
            {'message': message, 'errors': errors, 'code': code},
            status_code=status_code,
            headers=headers,
            indent=indent,
            default=default,
            encoder_class=encoder_class,
        )
