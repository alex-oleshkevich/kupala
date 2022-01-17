import pathlib

from kupala.dispatching import ActionConfig, ViewResult, action_config
from kupala.requests import Request
from kupala.responses import PlainTextResponse
from kupala.routing import Route
from kupala.testclient import TestClient
from tests.conftest import TestAppFactory


def test_empty_renderer(test_app_factory: TestAppFactory) -> None:
    @action_config()
    def view() -> None:
        pass

    client = TestClient(test_app_factory(routes=[Route('/', view)]))
    response = client.get('/')
    assert response.status_code == 204


def test_text_renderer(test_app_factory: TestAppFactory) -> None:
    @action_config(renderer='text')
    def view() -> str:
        return 'content'

    client = TestClient(test_app_factory(routes=[Route('/', view)]))
    response = client.get('/')
    assert 'text/plain' in response.headers['content-type']
    assert client.get('/').text == 'content'


def test_html_renderer(test_app_factory: TestAppFactory) -> None:
    @action_config(renderer='html')
    def view() -> str:
        return 'content'

    client = TestClient(test_app_factory(routes=[Route('/', view)]))
    response = client.get('/')
    assert 'text/html' in response.headers['content-type']
    assert client.get('/').text == 'content'


def test_json_renderer(test_app_factory: TestAppFactory) -> None:
    @action_config(renderer='json')
    def view() -> str:
        return 'content'

    client = TestClient(test_app_factory(routes=[Route('/', view)]))
    response = client.get('/')
    assert 'application/json' in response.headers['content-type']
    assert client.get('/').text == '"content"'


def test_template_renderer(test_app_factory: TestAppFactory, tmpdir: pathlib.Path) -> None:
    with open(tmpdir / 'index.html', 'w') as f:
        f.write('content')

    @action_config(renderer='index.html')
    def view() -> dict:
        return {}

    client = TestClient(test_app_factory(template_dir=tmpdir, routes=[Route('/', view)]))
    response = client.get('/')
    assert 'text/html' in response.headers['content-type']
    assert client.get('/').text == 'content'


def test_view_renderer_no_action_for_response(test_app_factory: TestAppFactory) -> None:
    @action_config(renderer='json')
    def view() -> PlainTextResponse:
        return PlainTextResponse('content')

    client = TestClient(test_app_factory(routes=[Route('/', view)]))
    response = client.get('/')
    assert 'text/plain' in response.headers['content-type']
    assert client.get('/').text == 'content'


def test_custom_renderer(test_app_factory: TestAppFactory) -> None:
    def custom_renderer(request: Request, action_config: ActionConfig, view_result: ViewResult) -> PlainTextResponse:
        return PlainTextResponse('custom ' + view_result['content'])

    @action_config(renderer='custom')
    def view() -> str:
        return 'content'

    app = test_app_factory(routes=[Route('/', view)])
    app.view_renderer.add_renderer('custom', custom_renderer)
    client = TestClient(app)
    response = client.get('/')
    assert 'text/plain' in response.headers['content-type']
    assert client.get('/').text == 'custom content'
