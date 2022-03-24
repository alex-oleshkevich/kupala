import asyncio
import typing as t

from kupala.application import Kupala
from kupala.http.requests import Request
from kupala.http.responses import StreamingResponse
from kupala.testclient import TestClient


def test_streaming_response_with_async_generator() -> None:
    async def numbers() -> t.AsyncGenerator[str, None]:
        for x in range(1, 5):
            yield str(x)
            await asyncio.sleep(0)

    def view(request: Request) -> StreamingResponse:
        return StreamingResponse(numbers())

    app = Kupala()
    app.routes.add('/', view)

    client = TestClient(app)
    response = client.get('/')
    assert response.text == '1234'


def test_streaming_response_with_sync_generator() -> None:
    def numbers() -> t.Generator[str, None, None]:
        for x in range(1, 5):
            yield str(x)

    def view(request: Request) -> StreamingResponse:
        return StreamingResponse(numbers())

    app = Kupala()
    app.routes.add('/', view)

    client = TestClient(app)
    response = client.get('/')
    assert response.text == '1234'


def test_streaming_response_with_filename() -> None:
    async def numbers() -> t.AsyncGenerator[str, None]:
        for x in range(1, 5):
            yield str(x)
            await asyncio.sleep(0)

    def view(request: Request) -> StreamingResponse:
        return StreamingResponse(numbers(), media_type='text/plain', file_name='numbers.txt')

    app = Kupala()
    app.routes.add('/', view)

    client = TestClient(app)
    response = client.get('/')
    assert response.text == '1234'
    assert response.headers['content-disposition'] == 'attachment; filename="numbers.txt"'


def test_streaming_response_with_inline_disposition() -> None:
    async def numbers() -> t.AsyncGenerator[str, None]:
        for x in range(1, 5):
            yield str(x)
            await asyncio.sleep(0)

    def view(request: Request) -> StreamingResponse:
        return StreamingResponse(numbers(), media_type='text/plain', file_name='numbers.txt', inline=True)

    app = Kupala()
    app.routes.add('/', view)

    client = TestClient(app)
    response = client.get('/')
    assert response.text == '1234'
    assert response.headers['content-disposition'] == 'inline; filename="numbers.txt"'
