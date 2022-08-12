import os
from deesk.drivers.memory import MemoryDriver
from pathlib import Path

from kupala.http.routing import Routes
from kupala.storages.file_server import FileServer
from kupala.storages.storages import Storage
from tests.conftest import TestClientFactory


def test_file_server_attachment(
    tmp_path: Path, test_client_factory: TestClientFactory, routes: Routes, storage: Storage
) -> None:
    routes.mount("/media", FileServer(storage=storage))
    client = test_client_factory(routes=routes)
    response = client.get("/media/file.txt")
    assert response.status_code == 404

    tmp_file = tmp_path / "file.txt"
    tmp_file.write_text("content")
    response = client.get("/media/file.txt")
    assert response.status_code == 200
    assert response.text == "content"
    assert response.headers["content-disposition"] == 'attachment; filename="file.txt"'


def test_file_server_inline(
    tmp_path: Path, test_client_factory: TestClientFactory, routes: Routes, storage: Storage
) -> None:
    routes.mount("/media", FileServer(storage=storage, as_attachment=False))
    client = test_client_factory(routes=routes)

    tmp_file = tmp_path / "file.txt"
    tmp_file.write_text("content")
    response = client.get("/media/file.txt")
    assert response.status_code == 200
    assert response.text == "content"
    assert response.headers["content-disposition"] == 'inline; filename="file.txt"'


def test_file_server_allows_only_get(test_client_factory: TestClientFactory, routes: Routes, storage: Storage) -> None:
    routes.mount("/media", FileServer(storage=storage, as_attachment=False))
    client = test_client_factory(routes=routes)

    response = client.post("/media/file.txt")
    assert response.status_code == 405


def test_file_server_redirects_for_drivers_returning_urls(
    test_client_factory: TestClientFactory, routes: Routes
) -> None:
    class S3Storage(Storage):
        def url(self, path: str | os.PathLike) -> str:
            return "https://example.com"

    routes.mount("/media", FileServer(storage=S3Storage(MemoryDriver()), as_attachment=False))
    client = test_client_factory(routes=routes)

    response = client.get("/media/file.txt", allow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == "https://example.com"
