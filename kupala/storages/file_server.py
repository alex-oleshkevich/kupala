import os
from starlette.types import Receive, Scope, Send

from kupala.http.responses import FileResponse, PlainTextResponse, RedirectResponse, Response
from kupala.storages.storages import Storage


class FileServer:
    def __init__(self, storage: Storage, as_attachment: bool = True) -> None:
        self.storage = storage
        self.as_attachment = as_attachment

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        assert scope["type"] == "http"
        path = self.get_path(scope)
        response = await self.get_response(path, scope)
        await response(scope, receive, send)

    async def get_response(self, path: str, scope: Scope) -> Response:
        if scope["method"] not in ("GET", "HEAD"):
            return PlainTextResponse("Method Not Allowed", status_code=405)

        url = self.storage.url(path)
        if url.startswith('http'):
            return RedirectResponse(url, 307)
        path = self.storage.abspath(path)
        return FileResponse(path, inline=not self.as_attachment)

    def get_path(self, scope: Scope) -> str:
        return os.path.normpath(os.path.join(*scope["path"].split("/")))
