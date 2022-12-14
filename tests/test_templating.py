import jinja2
import pytest
import typing
from pathlib import Path
from starlette.datastructures import MutableHeaders

from kupala.requests import Request
from kupala.templating import Jinja2Templates, Library

template = """SIMPLE TEXT
FROM CONTEXT {{ context_variable }}
{% block main %}MAIN BLOCK CONTENT {{ block_var }}{% endblock %}
{% macro feature(name) %}MACRO {{ name }}{% endmacro %}"""


@pytest.fixture
def templates(tmp_path: Path) -> Path:
    template_file = tmp_path / "index.html"
    template_file.write_text(template)
    return tmp_path


@pytest.fixture
def jinja_env(templates: Path) -> jinja2.Environment:
    return jinja2.Environment(loader=jinja2.FileSystemLoader(templates))


@pytest.fixture
def library() -> Library:
    return Library()


def test_library_registry(library: Library) -> None:
    @library.filters.register("simple")
    def simple_filter(value: typing.Any) -> typing.Any:
        return value

    assert "simple" in library.filters.items


def test_library_registry_update(library: Library) -> None:
    def simple_filter(value: typing.Any) -> typing.Any:
        return value

    library.filters.update({"simple": simple_filter})
    assert "simple" in library.filters.items


def test_render_to_response(jinja_env: jinja2.Environment) -> None:
    request = Request(scope={"type": "http"})
    templates = Jinja2Templates(jinja_env)
    response = templates.TemplateResponse(
        request,
        "index.html",
        {"context_variable": "var"},
        status_code=400,
        headers={"x-custom": "value"},
        content_type="text/html2",
    )
    assert response.status_code == 400
    assert response.context == {"context_variable": "var", "request": request}  # type: ignore
    assert response.body == b"SIMPLE TEXT\nFROM CONTEXT var\nMAIN BLOCK CONTENT \n"
    assert response.media_type == "text/html2"
    assert response.headers == MutableHeaders(
        {"x-custom": "value", "content-length": "49", "content-type": "text/html2; charset=utf-8"}
    )


def test_render_to_response_with_context_processors(jinja_env: jinja2.Environment) -> None:
    def context_processor(request: Request) -> dict[str, typing.Any]:
        return {"context_variable": "from_context"}

    request = Request(scope={"type": "http"})
    templates = Jinja2Templates(jinja_env, context_processors=[context_processor])
    response = templates.TemplateResponse(request, "index.html")
    assert response.body == b"SIMPLE TEXT\nFROM CONTEXT from_context\nMAIN BLOCK CONTENT \n"


def test_render_to_response_with_inline_context_processors(jinja_env: jinja2.Environment) -> None:
    def context_processor(request: Request) -> dict[str, typing.Any]:
        return {"context_variable": "from_context"}

    request = Request(scope={"type": "http"})
    templates = Jinja2Templates(jinja_env)
    response = templates.TemplateResponse(request, "index.html", context_processors=[context_processor])
    assert response.body == b"SIMPLE TEXT\nFROM CONTEXT from_context\nMAIN BLOCK CONTENT \n"


def test_render_macro_to_response(jinja_env: jinja2.Environment) -> None:
    templates = Jinja2Templates(jinja_env)
    response = templates.TemplateMacroResponse("index.html", "feature", macro_kwargs={"name": "value"})
    assert response.body == b"MACRO value"


def test_render_to_string(jinja_env: jinja2.Environment) -> None:
    templates = Jinja2Templates(jinja_env)
    assert templates.render_to_string("index.html") == "SIMPLE TEXT\nFROM CONTEXT \nMAIN BLOCK CONTENT \n"


def test_render_block_to_string(jinja_env: jinja2.Environment) -> None:
    templates = Jinja2Templates(jinja_env)
    assert templates.render_block_to_string("index.html", "main") == "MAIN BLOCK CONTENT "


def test_render_macro_to_string(jinja_env: jinja2.Environment) -> None:
    templates = Jinja2Templates(jinja_env)
    assert templates.render_macro_to_string("index.html", "feature", {"name": "value"}) == "MACRO value"
