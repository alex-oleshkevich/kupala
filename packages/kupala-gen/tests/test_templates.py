import pathlib

import click
import pytest
from copier.errors import ForbiddenPathError

from kupala_gen.plans import CreateDirectory, CreateFile
from kupala_gen.sources import FileTemplate, resolve_template
from kupala_gen.templates import inspect_template, render_template


class TestInspectTemplate:
    def test_translates_the_supported_question_subset(self, tmp_path: pathlib.Path) -> None:
        source = tmp_path / "template"
        source.mkdir()
        source.joinpath("kupala.toml").write_text(
            """
_secret_questions = ["token"]
[enabled]
type = "bool"
default = false
[count]
type = "int"
default = 2
[kind]
type = "str"
choices = ["page", "api"]
help = "Kind of component"
[token]
type = "str"
required = false
[name]
type = "str"
when = "{{ enabled }}"
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
        source.joinpath("kupala.toml").write_text(
            '[enabled]\ntype = "bool"\ndefault = true\n[name]\nwhen = "enabled"\n'
            '[count]\ntype = "int"\ndefault = 1\n[label]\nwhen = "count"\n'
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
        source.joinpath("kupala.toml").write_text(f'{setting} = ["unsafe"]\n')

        with (
            resolve_template(FileTemplate(source.as_uri()), trust=True) as snapshot,
            pytest.raises(ValueError, match="Unsupported template setting"),
        ):
            inspect_template(snapshot)

    @pytest.mark.parametrize(
        ("configuration", "message"),
        [
            ('_secret_questions = "token"\n', "list of question names"),
            ('"" = {}\n', "Question names"),
            ('[name]\ntype = "bytes"\n', "Unsupported question type"),
            ("[name]\ntype = []\n", "Unsupported question type"),
            ('[name]\nchoices = "value"\n', "Choices"),
            ('[name]\nrequired = "value"\n', "Requiredness"),
            ('[name]\nsecret = "value"\n', "Secrecy"),
            ("[name]\nquestion = 1\n", "Prompt"),
            ('_secret_questions = ["missing"]\n', "Unknown secret question"),
            ("[name]\nwhen = true\n", "must be a string"),
        ],
    )
    def test_rejects_invalid_question_configuration(
        self, tmp_path: pathlib.Path, configuration: str, message: str
    ) -> None:
        source = tmp_path / str(abs(hash(configuration)))
        source.mkdir()
        source.joinpath("kupala.toml").write_text(configuration)

        with (
            resolve_template(FileTemplate(source.as_uri()), trust=True) as snapshot,
            pytest.raises((TypeError, ValueError), match=message),
        ):
            inspect_template(snapshot)

    def test_accepts_no_configuration_required_questions_and_scalar_defaults(self, tmp_path: pathlib.Path) -> None:
        empty = tmp_path / "empty"
        empty.mkdir()
        with resolve_template(FileTemplate(empty.as_uri()), trust=True) as snapshot:
            assert inspect_template(snapshot).questions == ()

        source = tmp_path / "template"
        source.mkdir()
        source.joinpath("kupala.toml").write_text("name = {}\ncount = 2\n")
        with resolve_template(FileTemplate(source.as_uri()), trust=True) as snapshot:
            questions = inspect_template(snapshot).questions
        assert questions[0].required
        assert questions[1].default == 2

    def test_rejects_invalid_toml(self, tmp_path: pathlib.Path) -> None:
        source = tmp_path / "template"
        source.mkdir()
        config = source / "kupala.toml"
        config.write_text("[")
        with (
            resolve_template(FileTemplate(source.as_uri()), trust=True) as snapshot,
            pytest.raises(ValueError, match="Could not read"),
        ):
            inspect_template(snapshot)

    def test_rejects_unknown_question_metadata_and_forward_conditions(self, tmp_path: pathlib.Path) -> None:
        source = tmp_path / "template"
        source.mkdir()
        config = source / "kupala.toml"
        config.write_text('[name]\ntype = "str"\ncustom = "value"\n')
        with (
            resolve_template(FileTemplate(source.as_uri()), trust=True) as snapshot,
            pytest.raises(ValueError, match="Unsupported metadata"),
        ):
            inspect_template(snapshot)

        config.write_text('[name]\nwhen = "{{ later }}"\n[later]\ntype = "str"\n')
        with (
            resolve_template(FileTemplate(source.as_uri()), trust=True) as snapshot,
            pytest.raises(ValueError, match="earlier questions"),
        ):
            inspect_template(snapshot)


class TestRenderTemplate:
    def test_renders_to_a_plan_without_writing_the_target(self, tmp_path: pathlib.Path) -> None:
        source = tmp_path / "template"
        source.mkdir()
        source.joinpath("kupala.toml").write_text('[name]\ntype = "str"\n')
        source.joinpath("copier.yml").write_text("_exclude: ['*']\n")
        source.joinpath("{{ name }}.txt.jinja").write_text("Hello {{ name }}\n")
        source.joinpath("asset.bin").write_bytes(b"\x00\xff")
        source.joinpath("empty").mkdir()
        nested = source / "nested"
        nested.mkdir()
        nested.joinpath("kupala.toml").write_text("nested\n")
        executable = source / "run.jinja"
        executable.write_text("#!/bin/sh\n")
        executable.chmod(0o755)
        target = tmp_path / "target"

        with resolve_template(FileTemplate(source.as_uri()), trust=True) as snapshot:
            plan = render_template(inspect_template(snapshot), {"name": "widget"})

        assert not target.exists()
        assert plan.operations == (
            CreateDirectory(pathlib.PurePath("empty"), mode=0o755),
            CreateDirectory(pathlib.PurePath("nested"), mode=0o755),
            CreateFile(pathlib.PurePath("asset.bin"), b"\x00\xff", mode=0o644),
            CreateFile(pathlib.PurePath("nested/kupala.toml"), b"nested\n", mode=0o644),
            CreateFile(pathlib.PurePath("run"), b"#!/bin/sh\n", mode=0o755),
            CreateFile(pathlib.PurePath("widget.txt"), b"Hello widget\n", mode=0o644),
        )

    def test_rejects_missing_answers_before_rendering(self, tmp_path: pathlib.Path) -> None:
        source = tmp_path / "template"
        source.mkdir()
        source.joinpath("kupala.toml").write_text('[name]\ntype = "str"\n')

        with (
            resolve_template(FileTemplate(source.as_uri()), trust=True) as snapshot,
            pytest.raises(click.UsageError, match="Missing required answers"),
        ):
            render_template(inspect_template(snapshot), {})

    def test_rejects_a_rendered_path_escape(self, tmp_path: pathlib.Path) -> None:
        source = tmp_path / "template"
        source.mkdir()
        source.joinpath("kupala.toml").write_text('[name]\ntype = "str"\n')
        source.joinpath("{{ name }}.jinja").write_text("content")

        with (
            resolve_template(FileTemplate(source.as_uri()), trust=True) as snapshot,
            pytest.raises(ForbiddenPathError),
        ):
            render_template(inspect_template(snapshot), {"name": "../outside"})

    def test_rejects_answer_files(self, tmp_path: pathlib.Path) -> None:
        source = tmp_path / "template"
        source.mkdir()
        source.joinpath("kupala.toml").write_text("")
        source.joinpath(".kupala-answers.toml.jinja").write_text("answers")
        with (
            resolve_template(FileTemplate(source.as_uri()), trust=True) as snapshot,
            pytest.raises(ValueError, match="answers file"),
        ):
            render_template(inspect_template(snapshot), {})
