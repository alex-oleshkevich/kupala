from kupala.application import Kupala
from tests.utils import FormatRenderer


def test_renderer() -> None:
    app = Kupala()
    app.renderer.use(FormatRenderer())
    assert app.renderer.render('hello %(name)s', {'name': 'world'}) == 'hello world'


def test_renderer_shortcut() -> None:
    app = Kupala()
    app.renderer.use(FormatRenderer())
    assert app.render('hello %(name)s', {'name': 'world'}) == 'hello world'
