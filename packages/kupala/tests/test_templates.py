import pathlib

import jinja2
import pytest

from kupala.requests import Request
from kupala.templates import Templates
from kupala.testutils import ScopeFactory


class TestJinjaTemplates:
    @pytest.fixture
    def templates(self) -> Templates:
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
        return Templates(environment)

    def test_binds_environment_arguments(self, templates: Templates) -> None:
        def double(value: str) -> str:
            return value + value

        def special(value: str) -> bool:
            return value == "Ada"

        configured = Templates(
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
        templates: Templates,
        scope_f: ScopeFactory,
    ) -> None:
        def add_context(request: Request) -> dict[str, str]:
            return {"from_processor": request.method}

        configured = Templates(
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
        templates: Templates,
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
        templates: Templates,
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
        templates: Templates,
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
        templates: Templates,
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

    def test_reads_a_template_object(self, templates: Templates) -> None:
        assert templates.get_template("string.html").render() == "Hello friend"


class TestTemplateLoaders:
    """Every way of telling `Templates` where templates live ends up in one choice loader."""

    def test_builds_an_environment_without_arguments(self) -> None:
        templates = Templates()

        with pytest.raises(jinja2.TemplateNotFound):
            templates.render("missing.html")

    def test_loads_templates_from_a_directory(self, tmp_path: pathlib.Path) -> None:
        (tmp_path / "from_disk.html").write_text("on disk")

        templates = Templates(directories=[str(tmp_path)])

        assert templates.render("from_disk.html") == "on disk"

    def test_loads_templates_from_a_package(self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
        # a package only qualifies if it ships a templates/ directory, so build one that does
        package = tmp_path / "packaged_templates"
        (package / "templates").mkdir(parents=True)
        (package / "__init__.py").write_text("")
        (package / "templates" / "packaged.html").write_text("from a package")
        monkeypatch.syspath_prepend(str(tmp_path))

        templates = Templates(packages=["packaged_templates"])

        assert templates.render("packaged.html") == "from a package"

    def test_a_directory_outranks_a_ready_made_loader(self, tmp_path: pathlib.Path) -> None:
        # what the application configured itself must win, or it can never override an extension
        (tmp_path / "page.html").write_text("APP")
        templates = Templates(
            directories=[str(tmp_path)],
            loaders=[jinja2.DictLoader({"page.html": "EXTENSION"})],
        )

        assert templates.render("page.html") == "APP"

    def test_accepts_ready_made_loaders(self) -> None:
        templates = Templates(loaders=[jinja2.DictLoader({"given.html": "given"})])

        assert templates.render("given.html") == "given"

    def test_add_loader_contributes_a_template(self) -> None:
        templates = Templates(loaders=[jinja2.DictLoader({"app.html": "app"})])

        templates.add_loader(jinja2.DictLoader({"extension.html": "extension"}))

        assert templates.render("extension.html") == "extension"

    def test_add_loader_does_not_shadow_an_existing_template(self) -> None:
        # an added loader goes last, so what the application already ships keeps winning
        templates = Templates(loaders=[jinja2.DictLoader({"page.html": "app"})])
        assert templates.render("page.html") == "app"

        templates.add_loader(jinja2.DictLoader({"page.html": "extension"}))

        assert templates.render("page.html") == "app"

    def test_add_loader_works_without_a_template_cache(self) -> None:
        environment = jinja2.Environment(loader=jinja2.DictLoader({}), cache_size=0, autoescape=True)
        templates = Templates(environment)

        templates.add_loader(jinja2.DictLoader({"late.html": "late"}))

        assert templates.render("late.html") == "late"

    def test_extends_a_supplied_environment(self) -> None:
        # the caller's own loader stays first, and the arguments extend it instead of being ignored
        environment = jinja2.Environment(loader=jinja2.DictLoader({"shared.html": "from env"}))
        templates = Templates(environment, loaders=[jinja2.DictLoader({"shared.html": "ours", "ours.html": "ours"})])

        assert templates.render("shared.html") == "from env"
        assert templates.render("ours.html") == "ours"

    def test_extends_a_supplied_environment_that_has_no_loader(self) -> None:
        templates = Templates(jinja2.Environment(), loaders=[jinja2.DictLoader({"ours.html": "ours"})])

        assert templates.render("ours.html") == "ours"


class TestTemplateEscaping:
    """Rendering user data must not be able to inject markup."""

    def test_escapes_html_by_default(self) -> None:
        templates = Templates(loaders=[jinja2.DictLoader({"page.html": "{{ value }}"})])

        rendered = templates.render("page.html", {"value": "<script>alert(1)</script>"})

        assert rendered == "&lt;script&gt;alert(1)&lt;/script&gt;"

    def test_escapes_html_in_a_response(self, scope_f: ScopeFactory) -> None:
        templates = Templates(loaders=[jinja2.DictLoader({"page.html": "{{ value }}"})])
        request = Request(scope_f())

        http_response = templates.render_to_response(request, "page.html", {"value": "<img onerror=x>"})

        assert b"<img" not in http_response.body
        assert http_response.body == b"&lt;img onerror=x&gt;"

    def test_escapes_html_in_a_supplied_environment(self) -> None:
        # an environment built elsewhere defaults to no escaping, and inheriting that silently
        # would turn every value rendered through it into an injection point
        environment = jinja2.Environment(loader=jinja2.DictLoader({"page.html": "{{ value }}"}))

        templates = Templates(environment)

        assert templates.env.autoescape is True
        assert templates.render("page.html", {"value": "<script>"}) == "&lt;script&gt;"

    def test_escaping_can_be_turned_off_deliberately(self) -> None:
        templates = Templates(loaders=[jinja2.DictLoader({"page.html": "{{ value }}"})], autoescape=False)

        assert templates.render("page.html", {"value": "<b>"}) == "<b>"

    def test_escapes_a_block(self) -> None:
        templates = Templates(loaders=[jinja2.DictLoader({"page.html": "{% block body %}{{ value }}{% endblock %}"})])

        assert templates.render_block("page.html", "body", {"value": "<b>"}) == "&lt;b&gt;"
