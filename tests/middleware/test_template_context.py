import pytest

from kupala.application import Kupala
from kupala.middleware import Middleware
from kupala.middleware.template_context import TemplateContextMiddleware
from kupala.requests import Request
from kupala.responses import JSONResponse
from kupala.testclient import TestClient


@pytest.mark.asyncio
async def test_template_context_middleware() -> None:
    async def view(request: Request) -> JSONResponse:
        return JSONResponse(request.state.template_context.keys())

    app = Kupala(
        middleware=[
            Middleware(TemplateContextMiddleware),
        ]
    )
    app.routes.add('/', view)

    client = TestClient(app)
    data = client.get('/').json()
    assert 'request' in data
    assert 'url' in data
    assert 'app' in data
    assert 'form_errors' in data
    assert 'old_input' in data


@pytest.mark.asyncio
async def test_template_context_middleware_with_custom_processor() -> None:
    def processor(request: Request) -> dict[str, str]:
        return {'custom': 'key'}

    async def view(request: Request) -> JSONResponse:
        return JSONResponse(list(request.state.template_context.keys()))

    app = Kupala(
        middleware=[
            Middleware(TemplateContextMiddleware, context_processors=[processor]),
        ]
    )
    app.routes.add('/', view)

    client = TestClient(app)
    data = client.get('/').json()
    assert 'custom' in data


@pytest.mark.asyncio
async def test_template_context_middleware_with_custom_async_processor() -> None:
    async def processor(request: Request) -> dict[str, str]:
        return {'custom': 'key'}

    async def view(request: Request) -> JSONResponse:
        return JSONResponse(list(request.state.template_context.keys()))

    app = Kupala(
        middleware=[
            Middleware(TemplateContextMiddleware, context_processors=[processor]),
        ]
    )
    app.routes.add('/', view)

    client = TestClient(app)
    data = client.get('/').json()
    assert 'custom' in data
