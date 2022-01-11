import typing
from starlette.testclient import TestClient as BaseTestClient

from kupala.application import Kupala

T = typing.TypeVar("T", bound=Kupala)


class TestClient(BaseTestClient, typing.Generic[T]):
    app: T
