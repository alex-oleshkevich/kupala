import jinja2
import pathlib
import pytest
import typing
from pathlib import Path
from starlette.applications import Starlette
from starlette.datastructures import MutableHeaders
from starlette.routing import Mount
from starlette.types import Receive, Scope, Send

from kupala.requests import Request
from kupala.templating import (
    Jinja2Templates,
    abs_url_for,
    app_processor,
    media_url,
    static_url,
    url_for,
    url_matches,
    url_processors,
)

template = """SIMPLE TEXT
FROM CONTEXT {{ context_variable }}
{% block main %}MAIN BLOCK CONTENT {{ block_var }}{% endblock %}
{% macro feature(name) %}MACRO {{ name }}{% endmacro -%}
{% macro feature_with_globals(name) %}MACRO {{name }} {{ global_name }}{% endmacro -%}
"""


async def simple_asgi_app(scope: Scope, receive: Receive, send: Send) -> None:  # pragma: no cover
    ...


@pytest.fixture
def templates_dir(tmp_path: Path) -> Path:
    template_file = tmp_path / "index.html"
    template_file.write_text(template)
    return tmp_path


@pytest.fixture
def jinja_env(templates_dir: pathlib.Path) -> jinja2.Environment:
    return jinja2.Environment(loader=jinja2.FileSystemLoader(templates_dir))


def test_render_to_response(jinja_env: jinja2.Environment) -> None:
    request = Request(scope={"type": "http"})
    templates = Jinja2Templates(env=jinja_env)
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


def test_context_processors(jinja_env: jinja2.Environment) -> None:
    def context_processor(request: Request) -> dict[str, typing.Any]:
        return {"context_variable": "from_context"}

    request = Request(scope={"type": "http"})
    templates = Jinja2Templates(env=jinja_env, context_processors=[context_processor])
    response = templates.TemplateResponse(request, "index.html")
    assert response.body == b"SIMPLE TEXT\nFROM CONTEXT from_context\nMAIN BLOCK CONTENT \n"


def test_render_to_string(jinja_env: jinja2.Environment) -> None:
    templates = Jinja2Templates(env=jinja_env)
    assert templates.render_to_string("index.html") == "SIMPLE TEXT\nFROM CONTEXT \nMAIN BLOCK CONTENT \n"


def test_render_block_to_string(jinja_env: jinja2.Environment) -> None:
    templates = Jinja2Templates(env=jinja_env)
    assert templates.render_block_to_string("index.html", "main") == "MAIN BLOCK CONTENT "


def test_render_macro_to_string(jinja_env: jinja2.Environment) -> None:
    templates = Jinja2Templates(env=jinja_env)
    assert templates.render_macro_to_string("index.html", "feature", {"name": "value"}) == "MACRO value"


def test_render_macro_to_string_with_globals(jinja_env: jinja2.Environment) -> None:
    templates = Jinja2Templates(env=jinja_env)
    assert (
        templates.render_macro_to_string(
            "index.html", "feature_with_globals", {"name": "value"}, globals={"global_name": "global"}
        )
        == "MACRO value global"
    )


def test_custom_plugins(jinja_env: jinja2.Environment, templates_dir: pathlib.Path) -> None:
    def plugin(env: jinja2.Environment) -> None:
        env.globals.update({"key": "value"})

    (templates_dir / "index.html").write_text("{{ key }}")
    templates = Jinja2Templates(env=jinja_env, plugins=[plugin])
    assert templates.render_to_string("index.html") == "value"


def test_context_processor_decorator(jinja_env: jinja2.Environment, templates_dir: pathlib.Path) -> None:
    (templates_dir / "index.html").write_text("{{ key }}")
    request = Request(scope={"type": "http"})
    templates = Jinja2Templates(env=jinja_env)

    @templates.context_processor
    def processor(request: Request) -> dict[str, typing.Any]:
        return {"key": "value"}

    response = templates.TemplateResponse(request, "index.html")
    assert response.body == b"value"


def test_filter_decorator(jinja_env: jinja2.Environment, templates_dir: pathlib.Path) -> None:
    (templates_dir / "index.html").write_text("{{ key|value }}")
    request = Request(scope={"type": "http"})
    templates = Jinja2Templates(env=jinja_env)

    @templates.filter()
    def value(value: str) -> str:
        return "filtered"

    response = templates.TemplateResponse(request, "index.html")
    assert response.body == b"filtered"


def test_filter_decorator_with_custom_name(jinja_env: jinja2.Environment, templates_dir: pathlib.Path) -> None:
    (templates_dir / "index.html").write_text("{{ key|to_value }}")
    request = Request(scope={"type": "http"})
    templates = Jinja2Templates(env=jinja_env)

    @templates.filter("to_value")
    def value(value: str) -> str:
        return "filtered"

    response = templates.TemplateResponse(request, "index.html")
    assert response.body == b"filtered"


def test_test_decorator(jinja_env: jinja2.Environment, templates_dir: pathlib.Path) -> None:
    (templates_dir / "index.html").write_text('{{ "true" is is_bool }}')
    request = Request(scope={"type": "http"})
    templates = Jinja2Templates(env=jinja_env)

    @templates.test()
    def is_bool(value: str) -> bool:
        return value == "true"

    response = templates.TemplateResponse(request, "index.html")
    assert response.body == b"True"


def test_test_decorator_with_custom_name(jinja_env: jinja2.Environment, templates_dir: pathlib.Path) -> None:
    (templates_dir / "index.html").write_text('{{ "true" is is_boolean }}')
    request = Request(scope={"type": "http"})
    templates = Jinja2Templates(env=jinja_env)

    @templates.test("is_boolean")
    def is_bool(value: str) -> bool:
        return value == "true"

    response = templates.TemplateResponse(request, "index.html")
    assert response.body == b"True"


def test_media_url() -> None:
    app = Starlette(
        routes=[
            Mount("/media", simple_asgi_app, name="media"),
            Mount("/custom-media", simple_asgi_app, name="custom_media"),
        ]
    )
    request = Request(scope={"type": "http", "app": app})
    assert media_url(request, "file.txt") == "/media/file.txt"
    assert media_url(request, "http://localhost/file.txt") == "http://localhost/file.txt"
    assert media_url(request, "file.txt", path_name="custom_media") == "/custom-media/file.txt"


def test_static_url() -> None:
    app = Starlette(
        routes=[
            Mount("/static", simple_asgi_app, name="static"),
            Mount("/custom-static", simple_asgi_app, name="custom_static"),
        ]
    )
    request = Request(scope={"type": "http", "app": app})
    assert static_url(request, "file.txt", append_timestamp=False) == "/static/file.txt"
    assert static_url(request, "file.txt").startswith("/static/file.txt?ts=")
    assert (
        static_url(request, "file.txt", append_timestamp=False, path_name="custom_static") == "/custom-static/file.txt"
    )

    # app in debug mod
    not_debug_url = static_url(request, "file.txt", append_timestamp=True)
    app.debug = True
    assert static_url(request, "file.txt", append_timestamp=True) != not_debug_url
    assert static_url(request, "file.txt", append_timestamp=True).startswith("/static/file.txt?ts=")


def test_url_for() -> None:
    app = Starlette(
        routes=[
            Mount("/media", simple_asgi_app, name="media"),
        ]
    )
    request = Request(scope={"type": "http", "app": app})
    assert url_for(request, "media", path="file") == "/media/file"


def test_abs_url_for() -> None:
    app = Starlette(
        routes=[
            Mount("/media", simple_asgi_app, name="media"),
        ]
    )
    request = Request(
        scope={
            "type": "http",
            "app": app,
            "router": app.router,
            "scheme": "http",
            "root_path": "",
            "headers": ((b"host", b"testserver"),),
        }
    )
    assert str(abs_url_for(request, "media", path="file")) == "http://testserver/media/file"


def test_url_matches() -> None:
    app = Starlette(
        routes=[
            Mount("/media", simple_asgi_app, name="media"),
        ]
    )
    request = Request(scope={"type": "http", "app": app, "root_path": "/media/file", "path": "", "headers": []})
    assert url_matches(request, "media", path_params={"path": "file"})
    assert url_matches(request, "media", path_params={"path": "file"}, exact=True)
    assert not url_matches(request, "media", path_params={"path": "file2"})
    assert url_matches(request, "media", path_params={"path": "fil"})
    assert not url_matches(request, "media", path_params={"path": "fil"}, exact=True)


@pytest.mark.asyncio
async def test_app_processor(jinja_env: jinja2.Environment) -> None:
    app = Starlette()
    request = Request(scope={"type": "http", "app": app})
    context = app_processor(request)
    assert "app" in context


@pytest.mark.asyncio
async def test_url_processors(jinja_env: jinja2.Environment) -> None:
    app = Starlette()
    request = Request(scope={"type": "http", "app": app})
    context = url_processors(request)
    assert "url" in context
    assert "abs_url" in context
    assert "static_url" in context
    assert "media_url" in context
    assert "url_matches" in context
