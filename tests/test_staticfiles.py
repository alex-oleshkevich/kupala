from pathlib import Path

from kupala.requests import Request
from kupala.responses import PlainTextResponse
from kupala.routing import Route
from kupala.testclient import TestClient
from tests.conftest import TestAppFactory


def test_staticfiles(test_app_factory: TestAppFactory, tmpdir: Path) -> None:
    asset_name = 'main.css'
    asset_path = Path(tmpdir / asset_name)
    asset_path.write_bytes(b'body {}')

    app = test_app_factory(static_dir=tmpdir)

    client = TestClient(app)
    assert app.storages.get('static') is not None  # test that storage created
    response = client.get('/static/' + asset_name)  # test that endpoint created and configured
    assert response.status_code == 200
    assert response.text == 'body {}'  # test that static files are served

    # test asset url generation
    assert app.static_url('main.css') == '/static/main.css'


def test_staticfiles_installs_jinja_callback(test_app_factory: TestAppFactory, tmpdir: Path) -> None:
    with open(tmpdir / 'index.html', 'w') as f:
        f.write('{{ static("main.css") }}')

    app = test_app_factory(template_dir=tmpdir, static_dir=tmpdir)

    assert app.render('index.html') == '/static/main.css'


def test_request_generates_static_url(test_app_factory: TestAppFactory, tmpdir: Path) -> None:
    def view(request: Request) -> PlainTextResponse:
        return PlainTextResponse(request.static_url('main.css'))

    app = test_app_factory(template_dir=tmpdir, routes=[Route('/', view)], static_dir=tmpdir)
    client = TestClient(app)
    assert client.get('/').text == '/static/main.css'
