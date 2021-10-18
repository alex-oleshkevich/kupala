from kupala.application import Kupala
from kupala.requests import Request
from kupala.responses import PlainTextResponse
from kupala.routing import Route
from kupala.testclient import TestClient


def sync_view(request: Request) -> PlainTextResponse:
    return PlainTextResponse("ok")


async def async_view(request: Request) -> PlainTextResponse:
    return PlainTextResponse("ok")


app = Kupala(
    routes=[
        Route("/sync", sync_view),
        Route("/async", async_view),
    ]
)
client = TestClient(app)


def test_calls_sync_view() -> None:
    response = client.get("/sync")
    assert response.status_code == 200
    assert response.text == "ok"


def test_calls_async_view() -> None:
    response = client.get("/async")
    assert response.status_code == 200
    assert response.text == "ok"
