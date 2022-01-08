from kupala.responses import Response
from kupala.routing import Route
from tests.conftest import TestAppFactory


def test_generates_urls(test_app_factory: TestAppFactory) -> None:
    def view() -> Response:
        return Response('')

    app = test_app_factory(
        routes=[
            Route('/example', view, name='example'),
            Route('/example-{key}', view, name='example-key'),
        ]
    )
    assert app.urls.url_for('example') == '/example'
    assert app.urls.url_for('example-key', key='key') == '/example-key'
