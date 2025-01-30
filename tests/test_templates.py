import jinja2
from starlette.requests import Request

from kupala.templating import Templates

jinja_env = jinja2.Environment(
    loader=jinja2.DictLoader(
        {
            "index.html": "Hello, {{ name }}!",
            "macro.html": "{% macro hello(name) %}Hello, {{ name }}!{% endmacro %}",
            "block.html": "{% block content %}Hello, {{ name }}!{% endblock %}",
        }
    ),
)


def test_render() -> None:
    templates = Templates(jinja_env=jinja_env)
    assert templates.render("index.html", {"name": "world"}) == "Hello, world!"


def test_render_macro() -> None:
    templates = Templates(jinja_env=jinja_env)
    assert (
        templates.render_macro("macro.html", "hello", {"name": "world"})
        == "Hello, world!"
    )


def test_render_block() -> None:
    templates = Templates(jinja_env=jinja_env)
    assert (
        templates.render_block("block.html", "content", {"name": "world"})
        == "Hello, world!"
    )


def test_render_to_response() -> None:
    templates = Templates(jinja_env=jinja_env)
    request = Request({"type": "http", "method": "GET", "url": "http://testserver/"})
    assert (
        templates.render_to_response(request, "index.html", {"name": "world"}).body
        == b"Hello, world!"
    )
