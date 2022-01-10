import jinja2
import pytest
import typing
from pathlib import Path

from kupala.application import Kupala


@pytest.fixture(autouse=True)
def create_templates(tmpdir: Path) -> typing.Generator[str, None, None]:
    with open(tmpdir / 'index.html', 'w') as f:
        f.write('hello {{ name }}')
        f.flush()

    yield str(tmpdir)


def test_jinja_custom_loader() -> None:
    app = Kupala()
    app.jinja.use_loader(jinja2.DictLoader({}))
    assert isinstance(app.jinja.loader, jinja2.DictLoader)


def test_jinja_custom_environment() -> None:
    env = jinja2.Environment()
    app = Kupala()
    app.jinja.use_env(env)
    assert app.jinja.env == env


def test_jinja_add_template_dir(create_templates: str) -> None:
    app = Kupala()
    app.jinja.add_template_dirs([create_templates])
    assert app.jinja.renderer.render('index.html', {'name': 'world'}) == 'hello world'


def test_jinja_add_globals(create_templates: str) -> None:
    app = Kupala()
    app.jinja.add_globals({'name': 'world'})
    assert 'name' in app.jinja.env.globals


def test_jinja_add_filters(create_templates: str) -> None:
    app = Kupala()
    app.jinja.add_filters({'titlecase': str.title})
    assert 'titlecase' in app.jinja.env.filters


def test_jinja_add_policies(create_templates: str) -> None:
    app = Kupala()
    app.jinja.add_policies({'mypolicy': True})
    assert 'mypolicy' in app.jinja.env.policies


def test_jinja_add_tests(create_templates: str) -> None:
    app = Kupala()
    app.jinja.add_tests({'mypolicy': True})
    assert 'mypolicy' in app.jinja.env.tests


def test_jinja_add_extension(create_templates: str) -> None:
    app = Kupala()
    app.jinja.add_extensions('jinja2.ext.debug')
    assert 'jinja2.ext.DebugExtension' in app.jinja.env.extensions


def test_jinja_configure() -> None:
    app = Kupala()
    app.jinja.configure(
        template_dirs=['/tmp'],
        globals={'test': True},
        filters={'test': str},
        policies={'test': True},
        tests={'test': str},
        extensions=['jinja2.ext.DebugExtension'],
    )
    assert '/tmp' in app.jinja.env.loader.searchpath  # type: ignore
    assert 'test' in app.jinja.env.globals
    assert 'test' in app.jinja.env.filters
    assert 'test' in app.jinja.env.policies
    assert 'jinja2.ext.DebugExtension' in app.jinja.env.extensions
