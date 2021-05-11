import typing as t

from starlette import responses

from . import json


class Response(responses.Response):
    ...


class TextResponse(responses.PlainTextResponse):
    ...


class HTMLResponse(responses.HTMLResponse):
    ...


class FileResponse(responses.FileResponse):
    ...


class StreamingResponse(responses.StreamingResponse):
    ...


class RedirectResponse(responses.RedirectResponse):
    ...


class JSONResponse(responses.Response):
    def __init__(
        self,
        content: t.Any,
        status_code: int = 200,
        headers: dict = None,
        indent: int = None,
        default: t.Callable = json.json_default,
        encoder_class: t.Type[json.JSONEncoder] = json.JSONEncoder,
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
