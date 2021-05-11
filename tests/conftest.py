import pytest
from starlette.testclient import TestClient

from kupala.application import App


@pytest.fixture()
def app() -> App:
    return App()


@pytest.fixture()
def test_client(app):
    return TestClient(app)
