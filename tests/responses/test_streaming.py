import asyncio
import typing as t

from kupala.http import Routes
from kupala.http.requests import Request
from kupala.http.responses import StreamingResponse
from kupala.testclient import TestClient
from tests.conftest import TestAppFactory


def test_streaming_response_with_async_generator(test_app_factory: TestAppFactory, routes: Routes) -> None:
    async def numbers() -> t.AsyncGenerator[str, None]:
        for x in range(1, 5):
            yield str(x)
            await asyncio.sleep(0)

    def view(request: Request) -> StreamingResponse:
        return StreamingResponse(numbers())

    routes.add("/", view)
    app = test_app_factory(routes=routes)

    client = TestClient(app)
    response = client.get("/")
    assert response.text == "1234"


def test_streaming_response_with_sync_generator(test_app_factory: TestAppFactory, routes: Routes) -> None:
    def numbers() -> t.Generator[str, None, None]:
        for x in range(1, 5):
            yield str(x)

    def view(request: Request) -> StreamingResponse:
        return StreamingResponse(numbers())

    routes.add("/", view)
    app = test_app_factory(routes=routes)

    client = TestClient(app)
    response = client.get("/")
    assert response.text == "1234"


def test_streaming_response_with_filename(test_app_factory: TestAppFactory, routes: Routes) -> None:
    async def numbers() -> t.AsyncGenerator[str, None]:
        for x in range(1, 5):
            yield str(x)
            await asyncio.sleep(0)

    def view(request: Request) -> StreamingResponse:
        return StreamingResponse(numbers(), media_type="text/plain", file_name="numbers.txt")

    routes.add("/", view)
    app = test_app_factory(routes=routes)

    client = TestClient(app)
    response = client.get("/")
    assert response.text == "1234"
    assert response.headers["content-disposition"] == 'attachment; filename="numbers.txt"'


def test_streaming_response_with_inline_disposition(test_app_factory: TestAppFactory, routes: Routes) -> None:
    async def numbers() -> t.AsyncGenerator[str, None]:
        for x in range(1, 5):
            yield str(x)
            await asyncio.sleep(0)

    def view(request: Request) -> StreamingResponse:
        return StreamingResponse(numbers(), media_type="text/plain", file_name="numbers.txt", inline=True)

    routes.add("/", view)
    app = test_app_factory(routes=routes)

    client = TestClient(app)
    response = client.get("/")
    assert response.text == "1234"
    assert response.headers["content-disposition"] == 'inline; filename="numbers.txt"'
