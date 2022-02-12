from pathlib import Path

from kupala.application import Kupala
from kupala.responses import Response
from kupala.routing import Route
from tests.conftest import TestAppFactory


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
            Route('/example-{key}', view, name='example-key'),
        ]
    )
    assert app.url_for('example') == '/example'
    assert app.url_for('example-key', key='key') == '/example-key'


def test_user_password_hasher() -> None:
    app = Kupala()
    app.use_password_hasher('pbkdf2_sha512')

    assert getattr(app.state, 'password_hasher')
    hashed = app.state.password_hasher.hash('password')
    assert app.state.password_hasher.verify('password', hashed)


def test_use_jinja_renderer() -> None:
    app = Kupala()
    app.use_jinja_renderer(
        template_dirs=['/tmp'],
        tests={'test': str},
        filters={'test': str},
        globals={'test': True},
        policies={'test': True},
        extensions=['jinja2.ext.DebugExtension'],
    )
    assert '/tmp' in app.state.jinja_env.loader.searchpath  # type: ignore
    assert 'test' in app.state.jinja_env.globals
    assert 'test' in app.state.jinja_env.filters
    assert 'test' in app.state.jinja_env.policies
    assert 'jinja2.ext.DebugExtension' in app.state.jinja_env.extensions
