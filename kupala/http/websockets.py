from __future__ import annotations

import typing
from starlette import websockets

if typing.TYPE_CHECKING:
    from kupala.application import App


class WebSocket(websockets.WebSocket):
    @property
    def app(self) -> App:
        return self.scope["app"]
