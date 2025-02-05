from __future__ import annotations

from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.exceptions import ExceptionMiddleware
from starlette.middleware.gzip import GZipMiddleware
from starlette.middleware.httpsredirect import HTTPSRedirectMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from kupala.middleware.csrf import CSRFMiddleware
from kupala.middleware.method_override import MethodOverrideMiddleware
from kupala.middleware.request_id import RequestIDMiddleware
from kupala.middleware.request_limit import RequestLimitMiddleware
from kupala.middleware.timeout import TimeoutMiddleware

__all__ = [
    "Middleware",
    "CSRFMiddleware",
    "RequestLimitMiddleware",
    "MethodOverrideMiddleware",
    "TimeoutMiddleware",
    "ExceptionMiddleware",
    "GZipMiddleware",
    "CORSMiddleware",
    "TrustedHostMiddleware",
    "HTTPSRedirectMiddleware",
    "RequestIDMiddleware",
]
