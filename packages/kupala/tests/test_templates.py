import jinja2
import pytest

from kupala.requests import Request
from kupala.templates import JinjaTemplates
from kupala.testutils import ScopeFactory


class TestJinjaTemplates:
    @pytest.fixture
    def templates(self) -> JinjaTemplates:
        environment = jinja2.Environment(
            loader=jinja2.DictLoader(
                {
                    "page.html": "{% block content %}Hello {{ name|default('friend') }}!{% endblock %}",
                    "macros.html": "{% macro greeting(name='friend') %}Hello {{ name }}!{% endmacro %}",
                    "string.html": "Hello {{ name|default('friend') }}",
                    "response.html": "{{ request.method }} {{ name|default('friend') }}",
                    "configured.html": "{% if name is special %}{{ greeting }} {{ name|double }}{% endif %}{% do values.append('done') %}{{ values|length }}",
                    "processor.html": "{{ from_processor }}",
                },
            ),
        )
        return JinjaTemplates(environment)

    def test_binds_environment_arguments(self, templates: JinjaTemplates) -> None:
        def double(value: str) -> str:
            return value + value

        def special(value: str) -> bool:
            return value == "Ada"

        configured = JinjaTemplates(
            templates.env,
            filters={"double": double},
            globals={"greeting": "Hello"},
            tests={"special": special},
            extensions=("jinja2.ext.do",),
        )

        assert configured.env.filters["double"] is double
        assert configured.env.globals["greeting"] == "Hello"
        assert configured.env.tests["special"] is special
        assert configured.render("configured.html", {"name": "Ada", "values": []}) == "Hello AdaAda1"

    def test_binds_context_processors(
        self,
        templates: JinjaTemplates,
        scope_f: ScopeFactory,
    ) -> None:
        def add_context(request: Request) -> dict[str, str]:
            return {"from_processor": request.method}

        configured = JinjaTemplates(
            templates.env,
            context_processors=(add_context,),
        )
        request = Request(scope_f())

        http_response = configured.render_to_response(request, "processor.html")

        assert http_response.body == b"GET"

    @pytest.mark.parametrize(
        ("context", "expected"),
        ((None, "Hello friend!"), ({"name": "Ada"}, "Hello Ada!")),
    )
    def test_renders_a_block_with_context(
        self,
        templates: JinjaTemplates,
        context: dict[str, str] | None,
        expected: str,
    ) -> None:
        assert templates.render_block("page.html", "content", context) == expected

    @pytest.mark.parametrize(
        ("context", "expected"),
        ((None, "Hello friend!"), ({"name": "Ada"}, "Hello Ada!")),
    )
    def test_renders_a_macro_with_context(
        self,
        templates: JinjaTemplates,
        context: dict[str, str] | None,
        expected: str,
    ) -> None:
        assert templates.render_macro("macros.html", "greeting", context) == expected

    @pytest.mark.parametrize(
        ("context", "expected"),
        ((None, "Hello friend"), ({"name": "Ada"}, "Hello Ada")),
    )
    def test_renders_a_string(
        self,
        templates: JinjaTemplates,
        context: dict[str, str] | None,
        expected: str,
    ) -> None:
        assert templates.render("string.html", context) == expected

    @pytest.mark.parametrize(
        ("context", "expected"),
        ((None, b"GET friend"), ({"name": "Ada"}, b"GET Ada")),
    )
    def test_renders_a_response_with_request(
        self,
        templates: JinjaTemplates,
        scope_f: ScopeFactory,
        context: dict[str, str] | None,
        expected: bytes,
    ) -> None:
        request = Request(scope_f())

        http_response = templates.render_to_response(
            request,
            "response.html",
            context,
            status_code=201,
            headers={"X-Test": "yes"},
            media_type="text/plain",
        )

        assert http_response.status_code == 201
        assert http_response.headers["x-test"] == "yes"
        assert http_response.headers["content-type"] == "text/plain; charset=utf-8"
        assert http_response.body == expected
