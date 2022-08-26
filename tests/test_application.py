from pathlib import Path

from kupala.http import route
from kupala.http.responses import Response
from tests.conftest import TestAppFactory


def test_application_renders(test_app_factory: TestAppFactory, tmp_path: Path) -> None:
    with open(tmp_path / "index.html", "w") as f:
        f.write("<html>{{ key }}</html>")
    app = test_app_factory()
    assert app.render("index.html") == "<html></html>"
    assert app.render("index.html", {"key": "value"}) == "<html>value</html>"


def test_application_url_for(test_app_factory: TestAppFactory) -> None:
    @route("/example", name="example")
    def view() -> Response:
        return Response("")

    @route("/example-{key}", name="example-key")
    def key_view() -> Response:
        return Response("")

    app = test_app_factory(routes=[view, key_view])
    assert app.url_for("example") == "/example"
    assert app.url_for("example-key", key="key") == "/example-key"
