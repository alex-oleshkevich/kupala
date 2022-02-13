import asyncio
import os
import pathlib
import typing as t
from json import JSONEncoder
from starlette.testclient import TestClient

from kupala.application import Kupala
from kupala.requests import Request
from kupala.responses import Response
from kupala.shortcuts import response
from tests.utils import FormatRenderer


def test_sends_file(tmpdir: os.PathLike) -> None:
    file_path = os.path.join(tmpdir, 'file.bin')
    with open(str(file_path), 'wb') as f:
        f.write(b'content')

    def view(request: Request) -> Response:
        return response(request).send_file(file_path, file_name='file.bin')

    app = Kupala()
    app.routes.add('/', view)

    client = TestClient(app)
    res = client.get('/')
    assert res.content == b'content'
    assert res.headers['content-disposition'] == 'attachment; filename="file.bin"'


def test_sends_inline(tmpdir: os.PathLike) -> None:
    file_path = os.path.join(tmpdir, 'file.bin')
    with open(str(file_path), 'wb') as f:
        f.write(b'content')

    def view(request: Request) -> Response:
        return response(request).send_file(file_path, file_name='file.bin', inline=True)

    app = Kupala()
    app.routes.add('/', view)

    client = TestClient(app)
    res = client.get('/')
    assert res.content == b'content'
    assert res.headers['content-disposition'] == 'inline; filename="file.bin"'


def test_accepts_path_class(tmpdir: os.PathLike) -> None:
    file_path = os.path.join(tmpdir, 'file.bin')
    with open(str(file_path), 'wb') as f:
        f.write(b'content')

    def view(request: Request) -> Response:
        return response(request).send_file(pathlib.Path(file_path), file_name='file.bin', inline=True)

    app = Kupala()
    app.routes.add('/', view)

    client = TestClient(app)
    res = client.get('/')
    assert res.content == b'content'
    assert res.headers['content-type'] == 'application/octet-stream'
    assert res.headers['content-disposition'] == 'inline; filename="file.bin"'


def test_html() -> None:
    def view(request: Request) -> Response:
        return response(request).html('<b>html text</b>')

    app = Kupala()
    app.routes.add('/', view)

    client = TestClient(app)
    res = client.get('/')
    assert res.headers['content-type'] == 'text/html; charset=utf-8'
    assert res.text == '<b>html text</b>'


class CustomObject:
    pass


def _default(o: t.Any) -> t.Any:
    if isinstance(o, CustomObject):
        return '<custom>'
    return o


class _JsonEncoder(JSONEncoder):
    def default(self, o: t.Any) -> t.Any:
        return _default(o)


def test_custom_encoder_class() -> None:
    def view(request: Request) -> Response:
        return response(request).json(
            {
                'object': CustomObject(),
            },
            encoder_class=_JsonEncoder,
        )

    app = Kupala()
    app.routes.add('/', view)

    client = TestClient(app)
    res = client.get('/')
    assert res.json() == {'object': '<custom>'}


def test_custom_default() -> None:
    def view(request: Request) -> Response:
        return response(request).json(
            {
                'object': CustomObject(),
            },
            default=_default,
        )

    app = Kupala()
    app.routes.add('/', view)

    client = TestClient(app)
    res = client.get('/')
    assert res.json() == {'object': '<custom>'}


def test_json() -> None:
    def view(request: Request) -> Response:
        return response(request).json(
            {'user': 'root'},
        )

    app = Kupala()
    app.routes.add('/', view)

    client = TestClient(app)
    res = client.get('/')
    assert res.json() == {'user': 'root'}


def test_json_indents() -> None:
    def view(request: Request) -> Response:
        return response(request, 201).json({'user': {'details': {'name': 'root'}}}, indent=4)

    app = Kupala()
    app.routes.add('/', view)

    client = TestClient(app)
    res = client.get('/')
    assert res.status_code == 201
    assert (
        res.text
        == """{
    "user":{
        "details":{
            "name":"root"
        }
    }
}"""
    )


def test_redirect() -> None:
    def view(request: Request) -> Response:
        return response(request).redirect('/about')

    app = Kupala()
    app.routes.add('/', view)

    client = TestClient(app)
    res = client.get('/', allow_redirects=False)
    assert res.status_code == 302
    assert res.headers['location'] == '/about'


def test_redirect_to_route_name() -> None:
    def view(request: Request) -> Response:
        return response(request).redirect(path_name='about')

    app = Kupala()
    app.routes.add('/', view)
    app.routes.add('/about', view, name='about')
    client = TestClient(app)
    res = client.get('/', allow_redirects=False)
    assert res.status_code == 302
    assert res.headers['location'] == 'http://testserver/about'


def test_streaming_response_with_async_gen() -> None:
    async def numbers() -> t.AsyncGenerator[str, None]:
        for x in range(1, 5):
            yield str(x)
            await asyncio.sleep(0)

    def view(request: Request) -> Response:
        return response(request).stream(numbers())

    app = Kupala()
    app.routes.add('/', view)

    client = TestClient(app)
    res = client.get('/')
    assert res.text == '1234'


def test_streaming_response_with_sync_gen() -> None:
    def numbers() -> t.Generator[str, None, None]:
        for x in range(1, 5):
            yield str(x)

    def view(request: Request) -> Response:
        return response(request).stream(numbers())

    app = Kupala()
    app.routes.add('/', view)

    client = TestClient(app)
    res = client.get('/')
    assert res.text == '1234'


def test_with_filename() -> None:
    async def numbers() -> t.AsyncGenerator[str, None]:
        for x in range(1, 5):
            yield str(x)
            await asyncio.sleep(0)

    def view(request: Request) -> Response:
        return response(request).stream(numbers(), content_type='text/plain', file_name='numbers.txt')

    app = Kupala()
    app.routes.add('/', view)

    client = TestClient(app)
    res = client.get('/')
    assert res.text == '1234'
    assert res.headers['content-disposition'] == 'attachment; filename="numbers.txt"'


def test_disposition_inline() -> None:
    async def numbers() -> t.AsyncGenerator[str, None]:
        for x in range(1, 5):
            yield str(x)
            await asyncio.sleep(0)

    def view(request: Request) -> Response:
        return response(request).stream(numbers(), content_type='text/plain', file_name='numbers.txt', inline=True)

    app = Kupala()
    app.routes.add('/', view)

    client = TestClient(app)
    res = client.get('/')
    assert res.text == '1234'
    assert res.headers['content-disposition'] == 'inline; filename="numbers.txt"'


def test_plain_text() -> None:
    def view(request: Request) -> Response:
        return response(request).text('plain text response')

    app = Kupala()
    app.routes.add('/', view)

    client = TestClient(app)
    res = client.get('/')
    assert res.headers['content-type'] == 'text/plain; charset=utf-8'
    assert res.text == 'plain text response'


def test_redirect_back() -> None:
    def view(request: Request) -> Response:
        return response(request).back()

    app = Kupala()
    app.routes.add('/', view)

    client = TestClient(app)
    res = client.get('/', headers={'referer': 'http://testserver/somepage'}, allow_redirects=False)
    assert res.status_code == 302
    assert res.headers['location'] == 'http://testserver/somepage'


def test_redirect_back_checks_origin() -> None:
    def view(request: Request) -> Response:
        return response(request).back()

    app = Kupala()
    app.routes.add('/', view)

    client = TestClient(app)
    res = client.get('/', headers={'referer': 'http://example.com/'}, allow_redirects=False)
    assert res.status_code == 302
    assert res.headers['location'] == '/'


def test_empty() -> None:
    def view(request: Request) -> Response:
        return response(request).empty()

    app = Kupala()
    app.routes.add('/', view)

    client = TestClient(app)
    res = client.get('/')
    assert res.status_code == 204


def test_template() -> None:
    def view(request: Request) -> Response:
        return response(request).template('hello world')

    app = Kupala()
    app.set_renderer(FormatRenderer())
    app.routes.add('/', view)

    client = TestClient(app)
    res = client.get('/')
    assert res.text == 'hello world'
