import pytest
from starlette.testclient import TestClient

from kupala.application import App


@pytest.fixture
def app_f():
    def factory() -> App:
        return App()

    return factory


@pytest.fixture()
def app(app_f) -> App:
    return app_f()


@pytest.fixture()
def test_client(app):
    return TestClient(app)
