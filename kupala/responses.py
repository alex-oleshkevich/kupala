import os
import typing as t
import urllib.parse
from starlette import responses

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
        default: t.Callable = json.json_default,
        encoder_class: t.Type[JSONEncoder] = None,
    ):
        self._indent = indent
        self._default = default
        self._encoder_class = encoder_class

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
        input_data: t.Any = None,
        path_name: str = None,
        path_params: dict = None,
        request: Request = None,
    ):
        if not any([url, path_name]):
            raise ValueError('Either "url" or "path_name" argument must be passed.')

        if path_name:
            if request:
                url = request.url_for(path_name, **(path_params or {}))
            else:
                raise ValueError('"path_name" requires "request" argument.')

        if input_data:
            if request and 'session' in request.scope:
                request.session[REDIRECT_INPUT_DATA_SESSION_KEY] = input_data
            else:
                raise ValueError('"input_data" requires "request" argument.')

        assert url
        super().__init__(url, status_code, headers)
