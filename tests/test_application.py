from pathlib import Path

from tests.conftest import TestAppFactory


def test_application_renders(test_app_factory: TestAppFactory, tmpdir: Path) -> None:
    with open(tmpdir / 'index.html', 'w') as f:
        f.write('<html>{{ key }}</html>')
    app = test_app_factory(template_dir=tmpdir)
    assert app.render('index.html') == '<html></html>'
    assert app.render('index.html', {'key': 'value'}) == '<html>value</html>'
