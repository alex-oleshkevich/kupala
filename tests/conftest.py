import typing

import pytest
from starlette.testclient import TestClient

from kupala.applications import Kupala
from kupala.routing import Routes


@pytest.fixture
def app() -> Kupala:
    return Kupala("tests", routes=Routes())


@pytest.fixture
def test_client(app: Kupala) -> typing.Generator[TestClient]:
    with TestClient(app) as client:
        yield client
