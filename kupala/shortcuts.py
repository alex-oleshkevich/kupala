from kupala.requests import Request
from kupala.response_factories import ResponseFactory


def response(request: Request, status_code: int = 200, headers: dict = None) -> ResponseFactory:
    return ResponseFactory(request, status_code, headers)
