import os
import typing as t
from deesk.drivers.memory import MemoryDriver
from pathlib import Path
from starlette.testclient import TestClient

from kupala.application import Kupala
from kupala.routing import Mount
from kupala.storages.file_server import FileServer
from kupala.storages.storages import LocalStorage, Storage


def test_file_server_attachment(tmp_path: Path) -> None:
    app = Kupala(
        routes=[Mount("/media", FileServer(storage='media'))],
    )
    app.storages.add('media', LocalStorage(tmp_path))
    client = TestClient(app)
    response = client.get('/media/file.txt')
    assert response.status_code == 404

    tmp_file = tmp_path / 'file.txt'
    tmp_file.write_text('content')
    response = client.get('/media/file.txt')
    assert response.status_code == 200
    assert response.text == 'content'
    assert response.headers['content-disposition'] == 'attachment; filename="file.txt"'


def test_file_server_inline(tmp_path: Path) -> None:
    app = Kupala(
        routes=[Mount("/media", FileServer(storage='media', as_attachment=False))],
    )
    app.storages.add('media', LocalStorage(tmp_path))
    client = TestClient(app)
    tmp_file = tmp_path / 'file.txt'
    tmp_file.write_text('content')
    response = client.get('/media/file.txt')
    assert response.status_code == 200
    assert response.text == 'content'
    assert response.headers['content-disposition'] == 'inline; filename="file.txt"'


def test_file_server_allows_only_get(tmp_path: Path) -> None:
    app = Kupala(
        routes=[Mount("/media", FileServer(storage='media', as_attachment=False))],
    )
    app.storages.add('media', LocalStorage(tmp_path))
    client = TestClient(app)
    response = client.post('/media/file.txt')
    assert response.status_code == 405


def test_file_server_redirects_for_drivers_returning_urls() -> None:
    class S3Storage(Storage):
        async def url(self, path: t.Union[str, os.PathLike]) -> str:
            return 'https://example.com'

    app = Kupala(routes=[Mount("/media", FileServer(storage='media', as_attachment=False))])
    app.storages.add('media', S3Storage(MemoryDriver()))
    client = TestClient(app)
    response = client.get('/media/file.txt', allow_redirects=False)
    assert response.status_code == 307
    assert response.headers['location'] == 'https://example.com'
