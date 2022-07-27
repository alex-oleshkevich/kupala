import os
import pathlib

from kupala.http import Routes
from kupala.http.requests import Request
from kupala.http.responses import FileResponse
from tests.conftest import TestClientFactory


def test_sends_file(tmpdir: pathlib.Path, test_client_factory: TestClientFactory, routes: Routes) -> None:
    file_path = os.path.join(tmpdir, 'file.bin')
    with open(str(file_path), 'wb') as f:
        f.write(b'content')

    def view(request: Request) -> FileResponse:
        return FileResponse(file_path, file_name='file.bin')

    routes.add('/', view)
    client = test_client_factory(routes=routes)
    response = client.get('/')
    assert response.content == b'content'
    assert response.headers['content-disposition'] == 'attachment; filename="file.bin"'


def test_sends_inline(tmpdir: pathlib.Path, test_client_factory: TestClientFactory, routes: Routes) -> None:
    file_path = os.path.join(tmpdir, 'file.bin')
    with open(str(file_path), 'wb') as f:
        f.write(b'content')

    def view(request: Request) -> FileResponse:
        return FileResponse(file_path, file_name='file.bin', inline=True)

    routes.add('/', view)
    client = test_client_factory(routes=routes)
    response = client.get('/')
    assert response.content == b'content'
    assert response.headers['content-disposition'] == 'inline; filename="file.bin"'


def test_accepts_path_class(tmpdir: pathlib.Path, test_client_factory: TestClientFactory, routes: Routes) -> None:
    file_path = os.path.join(tmpdir, 'file.bin')
    with open(str(file_path), 'wb') as f:
        f.write(b'content')

    def view(request: Request) -> FileResponse:
        return FileResponse(pathlib.Path(file_path), file_name='file.bin', inline=True)

    routes.add('/', view)
    client = test_client_factory(routes=routes)
    response = client.get('/')
    assert response.content == b'content'
    assert response.headers['content-type'] == 'application/octet-stream'
    assert response.headers['content-disposition'] == 'inline; filename="file.bin"'
