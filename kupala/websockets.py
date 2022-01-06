from starlette import websockets

from kupala.application import Kupala


class WebSocket(websockets.WebSocket):
    @property
    def app(self) -> Kupala:
        return self.scope["app"]
