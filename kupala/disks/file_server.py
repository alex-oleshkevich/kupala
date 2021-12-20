import os
from starlette.types import Receive, Scope, Send

from kupala.disks.storages import Storage, Storages
from kupala.responses import FileResponse, PlainTextResponse, RedirectResponse, Response


class FileServer:
    def __init__(self, disk: str = None, as_attachment: bool = True) -> None:
        self.disk = disk
        self.as_attachment = as_attachment

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        assert scope["type"] == "http"
        path = self.get_path(scope)
        response = await self.get_response(path, scope)
        await response(scope, receive, send)

    async def get_response(self, path: str, scope: Scope) -> Response:
        if scope["method"] not in ("GET", "HEAD"):
            return PlainTextResponse("Method Not Allowed", status_code=405)

        url = await self.get_disk(scope).url(path)
        if url.startswith('http'):
            return RedirectResponse(url, 307)
        path = self.get_disk(scope).abspath(path)
        return FileResponse(path, inline=not self.as_attachment)

    def get_path(self, scope: Scope) -> str:
        return os.path.normpath(os.path.join(*scope["path"].split("/")))

    def get_disk(self, scope: Scope) -> Storage:
        storages = scope['app'].resolve(Storages)
        return storages.get_or_default(self.disk)
