import os
import pathlib
from starlette.testclient import TestClient

from kupala.application import Kupala
from kupala.requests import Request
from kupala.responses import FileResponse


def test_sends_file(tmpdir: pathlib.Path) -> None:
    file_path = os.path.join(tmpdir, 'file.bin')
    with open(str(file_path), 'wb') as f:
        f.write(b'content')

    def view(request: Request) -> FileResponse:
        return FileResponse(file_path, file_name='file.bin')

    app = Kupala()
    app.routes.get('/', view)

    client = TestClient(app)
    response = client.get('/')
    assert response.content == b'content'
    assert response.headers['content-disposition'] == 'attachment; filename="file.bin"'


def test_sends_inline(tmpdir: pathlib.Path) -> None:
    file_path = os.path.join(tmpdir, 'file.bin')
    with open(str(file_path), 'wb') as f:
        f.write(b'content')

    def view(request: Request) -> FileResponse:
        return FileResponse(file_path, file_name='file.bin', inline=True)

    app = Kupala()
    app.routes.get('/', view)

    client = TestClient(app)
    response = client.get('/')
    assert response.content == b'content'
    assert response.headers['content-disposition'] == 'inline; filename="file.bin"'


def test_accepts_path_class(tmpdir: pathlib.Path) -> None:
    file_path = os.path.join(tmpdir, 'file.bin')
    with open(str(file_path), 'wb') as f:
        f.write(b'content')

    def view(request: Request) -> FileResponse:
        return FileResponse(pathlib.Path(file_path), file_name='file.bin', inline=True)

    app = Kupala()
    app.routes.get('/', view)

    client = TestClient(app)
    response = client.get('/')
    assert response.content == b'content'
    assert response.headers['content-type'] == 'application/octet-stream'
    assert response.headers['content-disposition'] == 'inline; filename="file.bin"'
