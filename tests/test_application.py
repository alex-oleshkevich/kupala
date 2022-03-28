from pathlib import Path

from kupala.contracts import TemplateRenderer
from kupala.http.responses import Response
from kupala.http.routing import Route
from tests.conftest import TestAppFactory


def test_application_renders(
    test_app_factory: TestAppFactory, jinja_renderer: TemplateRenderer, jinja_template_path: Path
) -> None:
    with open(jinja_template_path / 'index.html', 'w') as f:
        f.write('<html>{{ key }}</html>')
    app = test_app_factory(renderer=jinja_renderer)
    assert app.render('index.html') == '<html></html>'
    assert app.render('index.html', {'key': 'value'}) == '<html>value</html>'


def test_application_url_for(test_app_factory: TestAppFactory) -> None:
    def view() -> Response:
        return Response('')

    app = test_app_factory(
        routes=[
            Route('/example', view, name='example'),
            Route('/example-{key}', view, name='example-key'),
        ]
    )
    assert app.url_for('example') == '/example'
    assert app.url_for('example-key', key='key') == '/example-key'
