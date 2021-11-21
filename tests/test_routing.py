from kupala.application import Kupala
from kupala.requests import Request
from kupala.responses import JSONResponse, PlainTextResponse
from kupala.routing import Route
from kupala.testclient import TestClient


def sync_view(request: Request) -> PlainTextResponse:
    return PlainTextResponse("ok")


async def async_view(request: Request) -> PlainTextResponse:
    return PlainTextResponse("ok")


async def path_params_view(id: int) -> PlainTextResponse:
    return PlainTextResponse(id)


class CustomRequest(Request):
    @property
    def request_type(self) -> str:
        return 'custom'


async def custom_request_class_view(request: CustomRequest) -> JSONResponse:
    return JSONResponse({'class': request.__class__.__name__, 'type': request.request_type})


class SomeService:
    ...


async def service_injection_view(service: SomeService) -> PlainTextResponse:
    return PlainTextResponse(service.__class__.__name__)


async def service_and_path_params_view(id: int, service: SomeService) -> JSONResponse:
    return JSONResponse({'id': id, 'service': service.__class__.__name__})


app = Kupala(
    routes=[
        Route("/sync", sync_view),
        Route("/async", async_view),
        Route("/users/{id}", path_params_view),
        Route("/service", service_injection_view),
        Route("/custom-request", custom_request_class_view),
        Route("/users/service/{id}", service_and_path_params_view),
    ]
)
app.services.bind(SomeService, SomeService())
client = TestClient(app)


def test_calls_sync_view() -> None:
    response = client.get("/sync")
    assert response.status_code == 200
    assert response.text == "ok"


def test_calls_async_view() -> None:
    response = client.get("/async")
    assert response.status_code == 200
    assert response.text == "ok"


def test_injects_path_params() -> None:
    response = client.get("/users/1")
    assert response.status_code == 200
    assert response.text == "1"


def test_injects_services() -> None:
    response = client.get("/service")
    assert response.status_code == 200
    assert response.text == "SomeService"


def test_injects_services_and_path_params() -> None:
    response = client.get("/users/service/2")
    assert response.status_code == 200
    assert response.json()['id'] == '2'
    assert response.json()['service'] == 'SomeService'


def test_custom_request_class() -> None:
    response = client.get("/custom-request")
    assert response.json() == {
        'class': 'CustomRequest',
        'type': 'custom',
    }
