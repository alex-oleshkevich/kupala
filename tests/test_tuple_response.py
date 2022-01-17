from starlette.testclient import TestClient

from kupala.dispatching import action_config
from kupala.routing import Route
from tests.conftest import TestAppFactory


def test_three_tuple(test_app_factory: TestAppFactory) -> None:
    @action_config(renderer='json')
    async def view() -> tuple[dict, int, dict]:
        return {'id': 1, 'service': 'content'}, 201, {'x-key': 'value'}

    client = TestClient(test_app_factory(routes=[Route('/', view)]))
    response = client.get("/")
    assert response.json() == {'id': 1, 'service': 'content'}
    assert 'x-key' in response.headers
    assert response.status_code == 201


def test_two_tuple(test_app_factory: TestAppFactory) -> None:
    @action_config(renderer='json')
    async def view() -> tuple[dict, int]:
        return {'id': 1, 'service': 'content'}, 201

    client = TestClient(test_app_factory(routes=[Route('/', view)]))
    response = client.get("/")
    assert response.json() == {'id': 1, 'service': 'content'}
    assert response.status_code == 201


def test_one_tuple(test_app_factory: TestAppFactory) -> None:
    @action_config(renderer='json')
    async def view() -> dict:
        return {'id': 1, 'service': 'content'}

    client = TestClient(test_app_factory(routes=[Route('/', view)]))
    response = client.get("/")
    assert response.json() == {'id': 1, 'service': 'content'}
    assert response.status_code == 200
