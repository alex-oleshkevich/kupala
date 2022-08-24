import os
import pathlib

from kupala.http import route
from kupala.http.requests import Request
from kupala.http.responses import FileResponse
from tests.conftest import TestClientFactory


def test_sends_as_attachment(tmpdir: pathlib.Path, test_client_factory: TestClientFactory) -> None:
    file_path = os.path.join(tmpdir, "file.bin")
    with open(str(file_path), "wb") as f:
        f.write(b"content")

    @route("/")
    def view(request: Request) -> FileResponse:
        return FileResponse(file_path, file_name="file.bin")

    client = test_client_factory(routes=[view])
    response = client.get("/")
    assert response.content == b"content"
    assert response.headers["content-disposition"] == 'attachment; filename="file.bin"'


def test_sends_inline(tmpdir: pathlib.Path, test_client_factory: TestClientFactory) -> None:
    file_path = os.path.join(tmpdir, "file.bin")
    with open(str(file_path), "wb") as f:
        f.write(b"content")

    @route("/")
    def view(request: Request) -> FileResponse:
        return FileResponse(file_path, file_name="file.bin", inline=True)

    client = test_client_factory(routes=[view])
    response = client.get("/")
    assert response.content == b"content"
    assert response.headers["content-disposition"] == 'inline; filename="file.bin"'


def test_accepts_path_class(tmpdir: pathlib.Path, test_client_factory: TestClientFactory) -> None:
    file_path = os.path.join(tmpdir, "file.bin")
    with open(str(file_path), "wb") as f:
        f.write(b"content")

    @route("/")
    def view(request: Request) -> FileResponse:
        return FileResponse(pathlib.Path(file_path), file_name="file.bin", inline=True)

    client = test_client_factory(routes=[view])
    response = client.get("/")
    assert response.content == b"content"
    assert response.headers["content-type"] == "application/octet-stream"
    assert response.headers["content-disposition"] == 'inline; filename="file.bin"'


def test_sends_generates_file_name(tmpdir: pathlib.Path, test_client_factory: TestClientFactory) -> None:
    file_path = os.path.join(tmpdir, "file.bin")
    with open(str(file_path), "wb") as f:
        f.write(b"content")

    @route("/")
    def view(request: Request) -> FileResponse:
        return FileResponse(file_path, inline=True)

    client = test_client_factory(routes=[view])
    response = client.get("/")
    assert response.content == b"content"
    assert response.headers["content-disposition"] == 'inline; filename="file.bin"'
