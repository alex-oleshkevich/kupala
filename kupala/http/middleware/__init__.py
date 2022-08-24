from __future__ import annotations

from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.gzip import GZipMiddleware
from starlette.middleware.httpsredirect import HTTPSRedirectMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .csrf import CSRFMiddleware
from .exception import ExceptionMiddleware
from .flash_messages import FlashMessagesMiddleware
from .locale import LocaleMiddleware
from .request_limit import RequestLimitMiddleware
from .stack import Middleware, MiddlewareStack
from .timeout import TimeoutMiddleware

__all__ = [
    "Middleware",
    "MiddlewareStack",
    "CSRFMiddleware",
    "FlashMessagesMiddleware",
    "LocaleMiddleware",
    "RequestLimitMiddleware",
    "TimeoutMiddleware",
    "ExceptionMiddleware",
    "GZipMiddleware",
    "CORSMiddleware",
    "TrustedHostMiddleware",
    "HTTPSRedirectMiddleware",
]
