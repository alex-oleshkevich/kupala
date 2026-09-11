import os
import pathlib

import click
import pytest

from kupala_gen import templates
from kupala_gen.plans import CreateDirectory, CreateFile
from kupala_gen.sources import FileTemplate, resolve_template
from kupala_gen.templates import inspect_template, render_template


class TestInspectTemplate:
    def test_translates_the_supported_question_subset(self, tmp_path: pathlib.Path) -> None:
        source = tmp_path / "template"
        source.mkdir()
        source.joinpath("copier.yml").write_text(
            """
_secret_questions: [token]
enabled:
  type: bool
  default: false
count:
  type: int
  default: 2
kind:
  type: str
  choices: [page, api]
  help: Kind of component
token:
  type: str
  required: false
name:
  type: str
  when: "{{ enabled }}"
""".lstrip()
        )

        with resolve_template(FileTemplate(source.as_uri()), trust=True) as snapshot:
            definition = inspect_template(snapshot)

        enabled, count, kind, token, name = definition.questions
        assert enabled.default is False
        assert count.default == 2
        assert kind.choices == ("page", "api")
        assert kind.prompt == "Kind of component"
        assert token.secret and not token.required
        assert name.when is not None
        assert name.when({"enabled": True})
        assert not name.when({"enabled": False})
        with pytest.raises(KeyError):
            name.when({})

    def test_accepts_plain_conditions_and_requires_a_boolean_result(self, tmp_path: pathlib.Path) -> None:
        source = tmp_path / "template"
        source.mkdir()
        source.joinpath("copier.yml").write_text(
            "enabled:\n  type: bool\n  default: true\nname:\n  when: enabled\n"
            "count:\n  type: int\n  default: 1\nlabel:\n  when: count\n"
        )

        with resolve_template(FileTemplate(source.as_uri()), trust=True) as snapshot:
            definition = inspect_template(snapshot)

        assert definition.questions[1].when is not None
        assert definition.questions[1].when({"enabled": True})
        assert definition.questions[3].when is not None
        with pytest.raises(TypeError, match="boolean"):
            definition.questions[3].when({"count": 1})

    @pytest.mark.parametrize("setting", ["_tasks", "_migrations", "_jinja_extensions", "_external_data"])
    def test_rejects_executable_or_external_configuration(self, tmp_path: pathlib.Path, setting: str) -> None:
        source = tmp_path / setting
        source.mkdir()
        source.joinpath("copier.yml").write_text(f"{setting}: [unsafe]\n")

        with (
            resolve_template(FileTemplate(source.as_uri()), trust=True) as snapshot,
            pytest.raises(ValueError, match="Unsupported Copier setting"),
        ):
            inspect_template(snapshot)

    @pytest.mark.parametrize(
        ("configuration", "message"),
        [
            ("_secret_questions: token\n", "list of question names"),
            ("1: null\n", "Unsupported Copier setting"),
            ('"": null\n', "Question names"),
            ("name:\n  type: bytes\n", "Unsupported question type"),
            ("name:\n  choices: value\n", "Choices"),
            ("name:\n  required: value\n", "Requiredness"),
            ("name:\n  secret: value\n", "Secrecy"),
            ("name:\n  question: 1\n", "Prompt"),
            ("_secret_questions: [missing]\n", "Unknown secret question"),
            ("name:\n  when: true\n", "must be a string"),
        ],
    )
    def test_rejects_invalid_question_configuration(
        self, tmp_path: pathlib.Path, configuration: str, message: str
    ) -> None:
        source = tmp_path / str(abs(hash(configuration)))
        source.mkdir()
        source.joinpath("copier.yml").write_text(configuration)

        with (
            resolve_template(FileTemplate(source.as_uri()), trust=True) as snapshot,
            pytest.raises((TypeError, ValueError), match=message),
        ):
            inspect_template(snapshot)

    def test_accepts_no_configuration_null_questions_and_scalar_defaults(self, tmp_path: pathlib.Path) -> None:
        empty = tmp_path / "empty"
        empty.mkdir()
        with resolve_template(FileTemplate(empty.as_uri()), trust=True) as snapshot:
            assert inspect_template(snapshot).questions == ()

        source = tmp_path / "template"
        source.mkdir()
        source.joinpath("copier.yml").write_text("name: null\ncount: 2\n")
        with resolve_template(FileTemplate(source.as_uri()), trust=True) as snapshot:
            questions = inspect_template(snapshot).questions
        assert questions[0].required
        assert questions[1].default == 2

    def test_rejects_multiple_documents_configuration_files_and_invalid_yaml(self, tmp_path: pathlib.Path) -> None:
        source = tmp_path / "template"
        source.mkdir()
        config = source / "copier.yml"
        config.write_text("{}\n---\n{}\n")
        with (
            resolve_template(FileTemplate(source.as_uri()), trust=True) as snapshot,
            pytest.raises(ValueError, match="one mapping"),
        ):
            inspect_template(snapshot)

        source.joinpath("copier.yaml").write_text("{}\n")
        with (
            resolve_template(FileTemplate(source.as_uri()), trust=True) as snapshot,
            pytest.raises(ValueError, match="more than one"),
        ):
            inspect_template(snapshot)

        source.joinpath("copier.yaml").unlink()
        config.write_text("[\n")
        with (
            resolve_template(FileTemplate(source.as_uri()), trust=True) as snapshot,
            pytest.raises(ValueError, match="Could not read"),
        ):
            inspect_template(snapshot)

    def test_rejects_unknown_question_metadata_and_forward_conditions(self, tmp_path: pathlib.Path) -> None:
        source = tmp_path / "template"
        source.mkdir()
        config = source / "copier.yml"
        config.write_text("name:\n  type: str\n  custom: value\n")
        with (
            resolve_template(FileTemplate(source.as_uri()), trust=True) as snapshot,
            pytest.raises(ValueError, match="Unsupported metadata"),
        ):
            inspect_template(snapshot)

        config.write_text('name:\n  when: "{{ later }}"\nlater:\n  type: str\n')
        with (
            resolve_template(FileTemplate(source.as_uri()), trust=True) as snapshot,
            pytest.raises(ValueError, match="earlier questions"),
        ):
            inspect_template(snapshot)


class TestRenderTemplate:
    def test_renders_to_a_plan_without_writing_the_target(self, tmp_path: pathlib.Path) -> None:
        source = tmp_path / "template"
        source.mkdir()
        source.joinpath("copier.yml").write_text("name:\n  type: str\n")
        source.joinpath("{{ name }}.txt.jinja").write_text("Hello {{ name }}\n")
        source.joinpath("asset.bin").write_bytes(b"\x00\xff")
        source.joinpath("empty").mkdir()
        executable = source / "run.jinja"
        executable.write_text("#!/bin/sh\n")
        executable.chmod(0o755)
        target = tmp_path / "target"

        with resolve_template(FileTemplate(source.as_uri()), trust=True) as snapshot:
            plan = render_template(inspect_template(snapshot), {"name": "widget"})

        assert not target.exists()
        assert plan.operations == (
            CreateDirectory(pathlib.PurePath("empty"), mode=0o755),
            CreateFile(pathlib.PurePath("asset.bin"), b"\x00\xff", mode=0o644),
            CreateFile(pathlib.PurePath("run"), b"#!/bin/sh\n", mode=0o755),
            CreateFile(pathlib.PurePath("widget.txt"), b"Hello widget\n", mode=0o644),
        )

    def test_rejects_missing_answers_before_rendering(self, tmp_path: pathlib.Path) -> None:
        source = tmp_path / "template"
        source.mkdir()
        source.joinpath("copier.yml").write_text("name:\n  type: str\n")

        with (
            resolve_template(FileTemplate(source.as_uri()), trust=True) as snapshot,
            pytest.raises(click.UsageError, match="Missing required answers"),
        ):
            render_template(inspect_template(snapshot), {})

    @pytest.mark.parametrize(
        "answers",
        [
            {"a": "parent", "b": "parent/child"},
            {"a": "parent/child", "b": "parent"},
        ],
    )
    def test_rejects_file_directory_collisions(self, tmp_path: pathlib.Path, answers: dict[str, str]) -> None:
        source = tmp_path / "template"
        source.mkdir()
        source.joinpath("copier.yml").write_text("a: null\nb: null\n")
        source.joinpath("{{ a }}.jinja").write_text("a")
        source.joinpath("{{ b }}.jinja").write_text("b")

        with (
            resolve_template(FileTemplate(source.as_uri()), trust=True) as snapshot,
            pytest.raises(ValueError, match="colliding destination"),
        ):
            render_template(inspect_template(snapshot), answers)

    @pytest.mark.parametrize("kind", ["symlink", "special"])
    def test_rejects_unsupported_rendered_entries(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, kind: str
    ) -> None:
        source = tmp_path / "template"
        source.mkdir()

        def render(source: str, destination: pathlib.Path, **kwargs: object) -> None:
            destination.mkdir()
            if kind == "symlink":
                destination.joinpath("entry").symlink_to("target")
            else:
                os.mkfifo(destination / "entry")

        monkeypatch.setattr(templates.copier, "run_copy", render)
        with (
            resolve_template(FileTemplate(source.as_uri()), trust=True) as snapshot,
            pytest.raises(ValueError, match="unsupported entry"),
        ):
            render_template(inspect_template(snapshot), {})

    def test_rejects_rendered_path_collisions_and_escapes(self, tmp_path: pathlib.Path) -> None:
        source = tmp_path / "template"
        source.mkdir()
        source.joinpath("copier.yml").write_text("name:\n  type: str\n")
        source.joinpath("{{ name }}.txt.jinja").write_text("one")
        source.joinpath("fixed.txt.jinja").write_text("two")

        with resolve_template(FileTemplate(source.as_uri()), trust=True) as snapshot:
            definition = inspect_template(snapshot)
            with pytest.raises(ValueError, match="colliding destination"):
                render_template(definition, {"name": "fixed"})
            with pytest.raises(ValueError, match="Unsafe rendered path"):
                render_template(definition, {"name": "../outside"})

    def test_rejects_answer_files(self, tmp_path: pathlib.Path) -> None:
        source = tmp_path / "template"
        source.mkdir()
        source.joinpath("copier.yml").write_text("{}\n")
        source.joinpath("{{ _copier_conf.answers_file }}.jinja").write_text("answers")

        with (
            resolve_template(FileTemplate(source.as_uri()), trust=True) as snapshot,
            pytest.raises(ValueError, match="answers file"),
        ):
            render_template(inspect_template(snapshot), {})

        source.joinpath("{{ _copier_conf.answers_file }}.jinja").unlink()
        source.joinpath(".copier-answers.yml.jinja").write_text("answers")
        with (
            resolve_template(FileTemplate(source.as_uri()), trust=True) as snapshot,
            pytest.raises(ValueError, match="answers file"),
        ):
            render_template(inspect_template(snapshot), {})

    def test_rejects_unicode_normalized_rendered_collisions(self, tmp_path: pathlib.Path) -> None:
        source = tmp_path / "template"
        source.mkdir()
        source.joinpath("copier.yml").write_text("a: null\nb: null\n")
        source.joinpath("{{ a }}.jinja").write_text("one")
        source.joinpath("{{ b }}.jinja").write_text("two")

        with (
            resolve_template(FileTemplate(source.as_uri()), trust=True) as snapshot,
            pytest.raises(ValueError, match="colliding destination"),
        ):
            render_template(
                inspect_template(snapshot),
                {"a": "é", "b": "e\N{COMBINING ACUTE ACCENT}"},
            )
