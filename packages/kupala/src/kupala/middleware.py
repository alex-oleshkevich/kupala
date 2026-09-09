import typing

from kupala.requests import Request
from kupala.responses import Response
from kupala.websockets import WebSocket

type CallNext = typing.Callable[[Request], typing.Awaitable[Response]]
type WebSocketCallNext = typing.Callable[[WebSocket], typing.Awaitable[None]]

type Middleware = typing.Callable[
    typing.Concatenate[Request, CallNext, ...],
    typing.Awaitable[Response],
]
type WebSocketMiddleware = typing.Callable[
    typing.Concatenate[WebSocket, WebSocketCallNext, ...],
    typing.Awaitable[None],
]
