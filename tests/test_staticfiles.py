from pathlib import Path

from kupala.contracts import TemplateRenderer
from kupala.http.requests import Request
from kupala.http.responses import PlainTextResponse
from kupala.http.routing import Routes
from kupala.testclient import TestClient
from tests.conftest import TestAppFactory


def test_staticfiles(test_app_factory: TestAppFactory, tmpdir: Path, routes: Routes) -> None:
    asset_name = 'main.css'
    asset_path = Path(tmpdir / asset_name)
    asset_path.write_bytes(b'body {}')

    routes.static('/static', tmpdir)
    app = test_app_factory(routes=routes)

    client = TestClient(app)
    response = client.get('/static/' + asset_name)  # test that endpoint created and configured
    assert response.status_code == 200
    assert response.text == 'body {}'  # test that static files are served

    # test asset url generation
    assert app.static_url('main.css') == '/static/main.css'


def test_staticfiles_installs_jinja_callback(
    test_app_factory: TestAppFactory,
    jinja_renderer: TemplateRenderer,
    jinja_template_path: Path,
    routes: Routes,
) -> None:
    with open(jinja_template_path / 'index.html', 'w') as f:
        f.write('{{ static("main.css") }}')

    routes.static('/static', jinja_template_path)
    app = test_app_factory(renderer=jinja_renderer, routes=routes)

    assert app.render('index.html') == '/static/main.css'


def test_request_generates_static_url(test_app_factory: TestAppFactory, tmpdir: Path, routes: Routes) -> None:
    def view(request: Request) -> PlainTextResponse:
        return PlainTextResponse(request.static_url('main.css'))

    routes.add('/', view)
    routes.static('/static', tmpdir)
    app = test_app_factory(routes=routes)
    client = TestClient(app)
    assert client.get('/').text == '/static/main.css'
