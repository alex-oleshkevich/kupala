import importlib.metadata

from starlette.testclient import TestClient

from kupala.applications import Kupala
from kupala.commands import Commands
from kupala.extensions import AppBuilder
from kupala.requests import Request
from kupala.responses import (
    FileResponse,
    HTMLResponse,
    JSONResponse,
    PlainTextResponse,
    RedirectResponse,
    Response,
    SSEResponse,
    StreamingResponse,
    response,
)
from kupala.routing import Routes
from kupala.security import APIKey, BasicAuth, BasicCredentials, Bearer, Identity, OAuth2

__all__ = [
    "APIKey",
    "AppBuilder",
    "BasicAuth",
    "BasicCredentials",
    "Bearer",
    "Commands",
    "FileResponse",
    "HTMLResponse",
    "Identity",
    "JSONResponse",
    "Kupala",
    "OAuth2",
    "PlainTextResponse",
    "RedirectResponse",
    "Request",
    "Response",
    "Routes",
    "SSEResponse",
    "StreamingResponse",
    "TestClient",
    "response",
]

__version__ = importlib.metadata.version("kupala")
