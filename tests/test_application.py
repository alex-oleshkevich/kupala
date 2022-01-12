import typing
from contextlib import asynccontextmanager
from pathlib import Path

from kupala.responses import Response
from kupala.routing import Route
from kupala.testclient import TestClient
from tests.conftest import TestApp, TestAppFactory


def test_application_renders(test_app_factory: TestAppFactory, tmpdir: Path) -> None:
    with open(tmpdir / 'index.html', 'w') as f:
        f.write('<html>{{ key }}</html>')
    app = test_app_factory(template_dir=tmpdir)
    assert app.render('index.html') == '<html></html>'
    assert app.render('index.html', {'key': 'value'}) == '<html>value</html>'


def test_application_url_for(test_app_factory: TestAppFactory, tmpdir: Path) -> None:
    def view() -> Response:
        return Response('')

    app = test_app_factory(
        routes=[
            Route('/example', view, name='example'),
        ]
    )
    assert app.urls.url_for('example') == '/example'


def test_lifespan(test_app_factory: TestAppFactory) -> None:
    enter_called = False
    exit_called = False

    @asynccontextmanager
    async def handler(app: TestApp) -> typing.AsyncIterator[None]:
        nonlocal enter_called, exit_called
        enter_called = True
        yield
        exit_called = True

    def view() -> Response:
        return Response('content')

    app = test_app_factory(lifespan_handlers=[handler])
    app.routes.add('/', view)

    with TestClient(app) as client:
        client.get('/')
        assert not exit_called
    assert enter_called
    assert exit_called


# def test_lifespan_boot_error(test_app_factory: TestAppFactory) -> None:
#     enter_called = False
#     exit_called = False
#
#     @asynccontextmanager
#     async def handler(app: TestApp) -> typing.AsyncIterator[None]:
#         nonlocal enter_called, exit_called
#         raise TypeError()
#         yield
#         exit_called = True
#
#     def view() -> Response:
#         return Response('content')
#
#     app = test_app_factory(lifespan_handlers=[handler])
#     app.routes.add('/', view)
#
#     with TestClient(app) as client:
#         client.get('/')
#         assert not exit_called
#     assert enter_called
#     assert exit_called
