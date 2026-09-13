import collections.abc
import contextlib
import importlib.metadata
import pathlib

import pytest
from click.testing import CliRunner

from kupala import cli
from kupala.commands import Commands
from kupala_gen import commands as commands_module
from kupala_gen.commands import build_gen_command
from kupala_gen.plugin import register
from kupala_gen.sources import GitTemplate, TemplateIdentity, TemplateSnapshot, TemplateSource


def install_plugin(monkeypatch: pytest.MonkeyPatch) -> None:
    point = importlib.metadata.EntryPoint(
        name="gen",
        value="kupala_gen.plugin:register",
        group=cli.PLUGIN_GROUP,
    )

    def entry_points(*, group: str) -> list[importlib.metadata.EntryPoint]:
        return [point] if group == cli.PLUGIN_GROUP else []

    monkeypatch.setattr(importlib.metadata, "entry_points", entry_points)


class TestRegister:
    def test_adds_the_generator_group(self) -> None:
        commands = Commands()
        register(commands)
        assert [command.name for command in commands.compile()] == ["gen", "new"]

    def test_the_group_lists_its_commands(self) -> None:
        gen = build_gen_command(Commands())
        result = CliRunner().invoke(gen, ["--help"])
        assert result.exit_code == 0
        assert "new" in result.output
        assert "add" in result.output

    def test_new_exposes_one_answer_option(self) -> None:
        result = CliRunner().invoke(build_gen_command(Commands()), ["new", "--help"])

        assert result.exit_code == 0
        assert "--answer KEY=VALUE" in result.output
        assert result.output.count("--answer") == 1

    def test_new_generates_the_minimal_template_from_both_paths(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        install_plugin(monkeypatch)
        runner = CliRunner()
        first = tmp_path / "123"
        second = tmp_path / "456"

        root_result = runner.invoke(
            cli.build_cli(None),
            ["new", str(first), "--template", "minimal", "--yes"],
        )
        nested_result = runner.invoke(
            cli.build_cli(None),
            ["gen", "new", str(second), "--template", "minimal", "--yes"],
        )

        assert root_result.exit_code == 0
        assert nested_result.exit_code == 0
        app = (first / "app.py").read_text()
        assert app == (second / "app.py").read_text()
        compile(app, "app.py", "exec")
        assert "routes = kupala.Routes()" in app
        assert "async def index_view" in app

    def test_new_generates_a_standard_project_by_default(self, tmp_path: pathlib.Path) -> None:
        destination = tmp_path / "hello-world"

        result = CliRunner().invoke(build_gen_command(Commands()), ["new", str(destination), "--yes"])

        assert result.exit_code == 0
        assert {path.relative_to(destination).as_posix() for path in destination.rglob("*") if path.is_file()} == {
            ".env",
            ".env.example",
            ".gitignore",
            "README.md",
            "hello_world/__init__.py",
            "hello_world/app.py",
            "hello_world/config.py",
            "hello_world/routes.py",
            "pyproject.toml",
            "tests/conftest.py",
            "tests/test_routes.py",
        }
        assert 'name = "hello-world"' in (destination / "pyproject.toml").read_text()
        assert 'app = "hello_world.app:app"' in (destination / "pyproject.toml").read_text()
        config = (destination / "hello_world/config.py").read_text()
        assert "class Settings(BaseSettings):" in config
        assert 'extra="ignore"' in config
        assert "async def index_view" in (destination / "hello_world/routes.py").read_text()
        assert "from kupala import TestClient" in (destination / "tests/conftest.py").read_text()

    def test_new_accepts_named_bundled_answers(self, tmp_path: pathlib.Path) -> None:
        destination = tmp_path / "project"

        result = CliRunner().invoke(
            build_gen_command(Commands()),
            ["new", str(destination), "--name", "Friendly", "--package", "friendly_app", "--yes"],
        )

        assert result.exit_code == 0
        assert 'name = "Friendly"' in (destination / "pyproject.toml").read_text()
        assert 'module-name = "friendly_app"' in (destination / "pyproject.toml").read_text()
        assert (destination / "friendly_app/app.py").is_file()

    @pytest.mark.parametrize(
        ("arguments", "message"),
        (
            (["--name", 'a"""b', "--package", "valid"], "project name"),
            (["--package", "not-valid"], "Python package name"),
            (["--answer", "package=not-valid"], "Python package name"),
        ),
    )
    def test_new_rejects_invalid_names(
        self,
        arguments: list[str],
        message: str,
        tmp_path: pathlib.Path,
    ) -> None:
        destination = tmp_path / "project"

        result = CliRunner().invoke(
            build_gen_command(Commands()),
            ["new", str(destination), *arguments, "--yes"],
        )

        assert result.exit_code == 2
        assert message in result.output
        assert not destination.exists()

    def test_new_generates_the_api_template(self, tmp_path: pathlib.Path) -> None:
        destination = tmp_path / "service"

        result = CliRunner().invoke(
            build_gen_command(Commands()),
            ["new", str(destination), "--template", "api", "--yes"],
        )

        assert result.exit_code == 0
        assert (destination / "service/api.py").is_file()
        assert "extensions=[api]" in (destination / "service/app.py").read_text()
        assert not (destination / "service/routes.py").exists()
        assert "async def index_view" in (destination / "service/api.py").read_text()
        assert "class Settings(BaseSettings):" in (destination / "service/config.py").read_text()
        assert 'client.get("/api/")' in (destination / "tests/test_api.py").read_text()
        assert not (destination / "tests/test_routes.py").exists()

    def test_new_generates_the_web_template(self, tmp_path: pathlib.Path) -> None:
        destination = tmp_path / "website"

        result = CliRunner().invoke(
            build_gen_command(Commands()),
            ["new", str(destination), "--template", "web", "--yes"],
        )

        assert result.exit_code == 0
        assert (destination / "website/templates/base.html").is_file()
        assert (destination / "website/templates/index.html").is_file()
        assert not (destination / "website/templates/error.html").exists()
        assert not (destination / "website/errors.py").exists()
        assert "class Settings(BaseSettings):" in (destination / "website/config.py").read_text()
        assert "async def index_view" in (destination / "website/routes.py").read_text()

    def test_new_generates_from_a_trusted_file_template(self, tmp_path: pathlib.Path) -> None:
        source = tmp_path / "template"
        source.mkdir()
        (source / "kupala.toml").write_text(
            '_secret_questions = ["token"]\n'
            'enabled = { type = "bool" }\n'
            'count = { type = "int" }\n'
            'label = { type = "str" }\n'
            'token = { type = "str" }\n'
        )
        (source / "values.txt.jinja").write_text("{{ enabled }}|{{ count }}|{{ label }}|{{ token }}\n")
        destination = tmp_path / "custom"

        result = CliRunner().invoke(
            build_gen_command(Commands()),
            [
                "new",
                str(destination),
                "--template",
                source.as_uri(),
                "--trust-template",
                "--answer",
                "enabled=false",
                "--answer",
                "count=0",
                "--answer",
                "label=",
                "--answer",
                "token=private-value",
                "--yes",
            ],
        )

        assert result.exit_code == 0
        assert (destination / "values.txt").read_text() == "False|0||private-value\n"
        assert "private-value" not in result.output

    def test_yes_does_not_trust_or_prompt_for_a_custom_template(self, tmp_path: pathlib.Path) -> None:
        source = tmp_path / "template"
        source.mkdir()
        (source / "file.txt").write_text("content")
        destination = tmp_path / "custom"

        result = CliRunner().invoke(
            build_gen_command(Commands()),
            ["new", str(destination), "--template", source.as_uri(), "--yes"],
        )

        assert result.exit_code == 2
        assert "not trusted" in result.output
        assert "Trust template" not in result.output
        assert not destination.exists()

    def test_custom_template_can_be_trusted_interactively(self, tmp_path: pathlib.Path) -> None:
        source = tmp_path / "template"
        source.mkdir()
        (source / "file.txt").write_text("content")
        destination = tmp_path / "custom"

        result = CliRunner().invoke(
            build_gen_command(Commands()),
            ["new", str(destination), "--template", source.as_uri(), "--dry-run"],
            input="y\n",
        )

        assert result.exit_code == 0
        assert "Trust template" in result.output
        assert not destination.exists()

    def test_new_passes_a_git_url_and_revision_to_the_source_resolver(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        source_root = tmp_path / "template"
        source_root.mkdir()
        (source_root / "file.txt").write_text("content")
        seen: list[TemplateSource] = []

        @contextlib.contextmanager
        def resolved(source: TemplateSource, **_: object) -> collections.abc.Iterator[TemplateSnapshot]:
            seen.append(source)
            yield TemplateSnapshot(TemplateIdentity("source", None, "resolved"), source_root)

        monkeypatch.setattr(commands_module, "resolve_template", resolved)
        revision = "a" * 40
        destination = tmp_path / "project"
        result = CliRunner().invoke(
            build_gen_command(Commands()),
            [
                "new",
                str(destination),
                "--template",
                "https://example.test/template.git",
                "--ref",
                revision,
                "--trust-template",
                "--yes",
            ],
        )

        assert result.exit_code == 0
        assert seen == [GitTemplate("https://example.test/template.git", revision)]

    @pytest.mark.parametrize(
        ("arguments", "message"),
        [
            (["--answer", "invalid"], "--answer must use KEY=VALUE"),
            (["--answer", "name=one", "--answer", "name=two"], "Duplicate answer: name"),
            (["--answer", "unknown=value"], "Unknown answer: unknown"),
            (["--answer", "name=one", "--name", "two"], "Duplicate answer: name"),
            (["--ref", "main"], "--ref is only valid for Git templates"),
        ],
    )
    def test_new_rejects_invalid_custom_answers(
        self,
        arguments: list[str],
        message: str,
        tmp_path: pathlib.Path,
    ) -> None:
        source = tmp_path / "template"
        source.mkdir()
        (source / "kupala.toml").write_text(
            '_secret_questions = ["token"]\nname = { default = "project" }\ntoken = { default = "safe" }\n'
        )
        (source / "value.txt.jinja").write_text("{{ name }}")
        destination = tmp_path / "custom"

        result = CliRunner().invoke(
            build_gen_command(Commands()),
            [
                "new",
                str(destination),
                "--template",
                source.as_uri(),
                "--trust-template",
                *arguments,
                "--yes",
            ],
        )

        assert result.exit_code == 2
        assert message in result.output

    def test_new_requires_custom_answers_in_yes_mode(self, tmp_path: pathlib.Path) -> None:
        source = tmp_path / "template"
        source.mkdir()
        (source / "kupala.toml").write_text('required = { type = "str" }\n')
        (source / "file.txt.jinja").write_text("{{ required }}")
        destination = tmp_path / "project"

        result = CliRunner().invoke(
            build_gen_command(Commands()),
            [
                "new",
                str(destination),
                "--template",
                source.as_uri(),
                "--trust-template",
                "--yes",
            ],
        )

        assert result.exit_code == 2
        assert "Missing required answers: required" in result.output

    def test_new_dry_run_does_not_write(self, tmp_path: pathlib.Path) -> None:
        destination = tmp_path / "project"

        runner = CliRunner()
        result = runner.invoke(
            build_gen_command(Commands()),
            ["new", str(destination), "--template", "minimal", "--dry-run", "--yes"],
        )
        with_diff = runner.invoke(
            build_gen_command(Commands()),
            ["new", str(destination), "--template", "minimal", "--dry-run", "--diff", "--yes"],
        )

        assert result.exit_code == 0
        assert "created" in result.output
        assert "--- a/" not in result.output
        assert "--- a/" in with_diff.output
        assert not destination.exists()

    def test_new_defaults_to_the_current_directory(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)

        result = CliRunner().invoke(
            build_gen_command(Commands()),
            ["new", "--template", "minimal", "--force", "--yes"],
        )

        assert result.exit_code == 0
        assert pathlib.Path("app.py").is_file()

    def test_new_requires_force_for_an_existing_destination(self, tmp_path: pathlib.Path) -> None:
        destination = tmp_path / "project"
        runner = CliRunner()
        arguments = ["new", str(destination), "--template", "minimal", "--yes"]

        assert runner.invoke(build_gen_command(Commands()), arguments).exit_code == 0
        existing = runner.invoke(build_gen_command(Commands()), arguments)
        unchanged = runner.invoke(build_gen_command(Commands()), [*arguments, "--force"])
        (destination / "app.py").write_text("changed\n")
        conflict = runner.invoke(build_gen_command(Commands()), [*arguments, "--force"])

        assert existing.exit_code == 2
        assert "Destination already exists" in existing.output
        assert unchanged.exit_code == 0
        assert "Applied 0 changes." in unchanged.output
        assert conflict.exit_code == 2
        assert (destination / "app.py").read_text() == "changed\n"

    def test_a_nested_group_needs_a_command(self) -> None:
        gen = build_gen_command(Commands())
        result = CliRunner().invoke(gen, ["add"])
        assert result.exit_code == 2

    def test_factory_builds_distinct_trees(self) -> None:
        first = build_gen_command(Commands())
        second = build_gen_command(Commands())

        assert first is not second
        assert first.commands["add"] is not second.commands["add"]
        assert first.commands["new"] is not second.commands["new"]

    @pytest.mark.parametrize(
        "application",
        [None, "malformed", "never.imported:app", "broken_gen_app:app"],
    )
    def test_bootstrap_commands_ignore_application_configuration(
        self,
        application: str | None,
        tmp_path: pathlib.Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        install_plugin(monkeypatch)
        monkeypatch.syspath_prepend(str(tmp_path))
        (tmp_path / "broken_gen_app.py").write_text("import secret_missing_dependency\n")
        if application is None:
            monkeypatch.delenv(cli.APP_ENV_VAR, raising=False)
        else:
            monkeypatch.setenv(cli.APP_ENV_VAR, application)

        runner = CliRunner()
        for args in (["gen", "--help"], ["gen", "new", "--help"], ["new", "--help"]):
            result = runner.invoke(cli.build_cli(None), args)

            assert result.exit_code == 0
            assert "secret_missing_dependency" not in result.output

        destination = tmp_path / "project"
        result = runner.invoke(
            cli.build_cli(None),
            ["new", str(destination), "--template", "minimal", "--yes"],
        )

        assert result.exit_code == 0
        assert (destination / "app.py").is_file()
