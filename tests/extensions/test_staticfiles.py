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

    app = test_app_factory()
    app.staticfiles.serve_from_directory(
        url_path='/statics', directory=tmpdir, storage_name='assets', path_name='assets', random_suffix=False
    )

    client = TestClient(app)
    assert app.storages.get('assets') is not None  # test that storage created
    response = client.get('/statics/' + asset_name)  # test that endpoint created and configured
    assert response.status_code == 200
    assert response.text == 'body {}'  # test that static files are served

    # test asset url generation
    assert app.staticfiles.static_url('main.css') == '/statics/main.css'


def test_staticfiles_with_url_prefix(test_app_factory: TestAppFactory, tmpdir: Path) -> None:
    app = test_app_factory()
    app.staticfiles.serve_from_directory(
        url_path='/statics',
        directory=tmpdir,
        url_prefix='http://example.com/',
        storage_name='assets',
        path_name='assets',
        random_suffix=False,
    )

    # test asset url generation
    assert app.staticfiles.static_url('main.css') == 'http://example.com/statics/main.css'


def test_staticfiles_installs_jinja_callback(test_app_factory: TestAppFactory, tmpdir: Path) -> None:
    with open(tmpdir / 'index.html', 'w') as f:
        f.write('{{ static("main.css") }}')

    app = test_app_factory(template_dir=tmpdir)
    app.staticfiles.serve_from_directory(
        url_path='/statics', directory=tmpdir, storage_name='assets', path_name='assets', random_suffix=False
    )

    assert app.renderer.render('index.html') == '/statics/main.css'


def test_request_generates_static_url(test_app_factory: TestAppFactory, tmpdir: Path) -> None:
    def view(request: Request) -> PlainTextResponse:
        return PlainTextResponse(request.static_url('main.css'))

    app = test_app_factory(template_dir=tmpdir, routes=[Route('/', view)])
    app.staticfiles.serve_from_directory(directory=tmpdir, random_suffix=False)
    client = TestClient(app)
    assert client.get('/').text == '/static/main.css'


def test_request_appends_random_suffix(test_app_factory: TestAppFactory, tmpdir: Path) -> None:
    app = test_app_factory(template_dir=tmpdir)
    app.staticfiles.serve_from_directory(directory=tmpdir, random_suffix=True)
    assert app.staticfiles.static_url('main.css') == f'/static/main.css?{app.staticfiles.start_time}'
