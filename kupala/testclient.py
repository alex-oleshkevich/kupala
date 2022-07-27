from starlette.testclient import TestClient as BaseTestClient

from kupala.application import App


class TestClient(BaseTestClient):
    app: App
