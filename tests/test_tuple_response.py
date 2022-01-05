import typing as t
from starlette.testclient import TestClient

from kupala.application import Kupala
from kupala.routing import Route


async def three_tuple_view() -> t.Tuple[dict, int, dict]:
    return {'id': 1, 'service': 'threetuple'}, 201, {'x-key': 'value'}


async def three_tuple__text_view() -> t.Tuple[str, int, dict]:
    return 'three tuple', 201, {'x-key': 'value'}


async def two_tuple_view() -> t.Tuple[dict, int]:
    return {'id': 1, 'service': 'threetuple'}, 201


async def two_tuple_text_view() -> t.Tuple[str, int]:
    return 'three tuple', 201


async def one_tuple_view() -> dict:
    return {'id': 1, 'service': 'threetuple'}


async def one_tuple_text_view() -> str:
    return 'three tuple'


app = Kupala(
    routes=[
        Route("/three-tuple", three_tuple_view),
        Route("/three-tuple-text", three_tuple__text_view),
        Route("/two-tuple", two_tuple_view),
        Route("/two-tuple-text", two_tuple_text_view),
        Route("/one-tuple", one_tuple_view),
        Route("/one-tuple-text", one_tuple_text_view),
    ]
)
client = TestClient(app)


def test_three_tuple() -> None:
    response = client.get("/three-tuple", headers={'accept': 'application/json'})
    assert response.json() == {'id': 1, 'service': 'threetuple'}
    assert 'x-key' in response.headers
    assert response.status_code == 201


def test_three_tuple_html() -> None:
    response = client.get("/three-tuple-text", headers={'accept': 'text/html'})
    assert response.text == 'three tuple'
    assert 'text/html' in response.headers['content-type']


def test_three_tuple_text() -> None:
    response = client.get("/three-tuple-text", headers={'accept': 'text/plain'})
    assert response.text == 'three tuple'
    assert 'text/plain' in response.headers['content-type']


def test_two_tuple() -> None:
    response = client.get("/two-tuple", headers={'accept': 'application/json'})
    assert response.json() == {'id': 1, 'service': 'threetuple'}
    assert response.status_code == 201


def test_two_tuple_html() -> None:
    response = client.get("/two-tuple-text", headers={'accept': 'text/html'})
    assert response.text == 'three tuple'
    assert 'text/html' in response.headers['content-type']


def test_two_tuple_text() -> None:
    response = client.get("/two-tuple-text", headers={'accept': 'text/plain'})
    assert response.text == 'three tuple'
    assert 'text/plain' in response.headers['content-type']


def test_one_tuple() -> None:
    response = client.get("/one-tuple", headers={'accept': 'application/json'})
    assert response.json() == {'id': 1, 'service': 'threetuple'}
    assert response.status_code == 200


def test_one_tuple_html() -> None:
    response = client.get("/one-tuple-text", headers={'accept': 'text/html'})
    assert response.text == 'three tuple'
    assert 'text/html' in response.headers['content-type']


def test_one_tuple_text() -> None:
    response = client.get("/one-tuple-text", headers={'accept': 'text/plain'})
    assert response.text == 'three tuple'
    assert 'text/plain' in response.headers['content-type']
