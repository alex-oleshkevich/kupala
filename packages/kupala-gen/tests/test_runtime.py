import dataclasses
import pathlib

import click
import pytest
from click.testing import CliRunner

from kupala_gen import runtime
from kupala_gen.plans import (
    ApplyError,
    ChangePlan,
    ConflictError,
    CreateDirectory,
    CreateFile,
    GenerationReport,
    OperationResult,
    OperationStatus,
    PreparedPlan,
    prepare_plan,
)
from kupala_gen.questions import InteractionMode, Question
from kupala_gen.runtime import ClickReporter, GenerationContext, generator, run_generation


class RecordingReporter:
    def __init__(self, *, confirmed: bool = True) -> None:
        self.confirmed = confirmed
        self.previews: list[PreparedPlan] = []
        self.reports: list[GenerationReport] = []

    def preview(self, plan: PreparedPlan) -> None:
        self.previews.append(plan)

    def confirm(self) -> bool:
        return self.confirmed

    def finish(self, report: GenerationReport) -> None:
        self.reports.append(report)


class TestRunGeneration:
    def test_resolves_answers_plans_and_applies(self, tmp_path: pathlib.Path) -> None:
        reporter = RecordingReporter()

        def plan(context: GenerationContext) -> ChangePlan:
            return ChangePlan((CreateFile("item.txt", str(context.answers["name"])),))

        report = run_generation(
            plan,
            target_root=tmp_path,
            questions=(Question("name", "Name"),),
            answers={"name": "widget"},
            yes=True,
            reporter=reporter,
        )

        assert (tmp_path / "item.txt").read_text() == "widget"
        assert report.operations[0].status is OperationStatus.CREATED
        assert len(reporter.previews) == len(reporter.reports) == 1

    def test_yes_never_prompts_and_fails_before_planning(self, tmp_path: pathlib.Path) -> None:
        planned = False

        def plan(context: GenerationContext) -> ChangePlan:
            nonlocal planned
            planned = True  # pragma: no cover - missing answers stop before planning
            return ChangePlan(())  # pragma: no cover - missing answers stop before planning

        with pytest.raises(click.UsageError, match="Missing required answers"):
            run_generation(
                plan,
                target_root=tmp_path,
                questions=(Question("name", "Name"),),
                yes=True,
                ask=lambda question: pytest.fail("prompted"),
            )

        assert not planned

    def test_dry_run_previews_without_writing_or_confirming(self, tmp_path: pathlib.Path) -> None:
        reporter = RecordingReporter(confirmed=False)

        report = run_generation(
            lambda context: ChangePlan((CreateFile("item.txt", "content"),)),
            target_root=tmp_path,
            dry_run=True,
            reporter=reporter,
        )

        assert report.operations[0].status is OperationStatus.CREATED
        assert not (tmp_path / "item.txt").exists()
        assert reporter.reports == []

    def test_non_interactive_application_requires_yes(self, tmp_path: pathlib.Path) -> None:
        with pytest.raises(click.UsageError, match="--yes"):
            run_generation(
                lambda context: ChangePlan((CreateFile("item.txt", "content"),)),
                target_root=tmp_path,
                interaction=InteractionMode.NON_INTERACTIVE,
            )

        assert list(tmp_path.iterdir()) == []

    def test_refused_confirmation_aborts_before_writes(self, tmp_path: pathlib.Path) -> None:
        with pytest.raises(click.Abort):
            run_generation(
                lambda context: ChangePlan((CreateFile("item.txt", "content"),)),
                target_root=tmp_path,
                interaction=InteractionMode.INTERACTIVE,
                reporter=RecordingReporter(confirmed=False),
            )

        assert list(tmp_path.iterdir()) == []

    def test_confirmed_interactive_run_applies(self, tmp_path: pathlib.Path) -> None:
        run_generation(
            lambda context: ChangePlan((CreateFile("item.txt", "content"),)),
            target_root=tmp_path,
            interaction=InteractionMode.INTERACTIVE,
            reporter=RecordingReporter(confirmed=True),
        )

        assert (tmp_path / "item.txt").exists()

    def test_unchanged_plan_needs_no_confirmation(self, tmp_path: pathlib.Path) -> None:
        (tmp_path / "item.txt").write_text("content")

        report = run_generation(
            lambda context: ChangePlan((CreateFile("item.txt", "content"),)),
            target_root=tmp_path,
            interaction=InteractionMode.NON_INTERACTIVE,
            reporter=RecordingReporter(confirmed=False),
        )

        assert report.operations[0].status is OperationStatus.UNCHANGED

    def test_hides_planner_exception_details(self, tmp_path: pathlib.Path) -> None:
        def plan(context: GenerationContext) -> ChangePlan:
            raise RuntimeError(f"failed with {context.answers['token']}")

        with pytest.raises(click.ClickException) as caught:
            run_generation(
                plan,
                target_root=tmp_path,
                questions=(Question("token", "Token", secret=True),),
                answers={"token": "top-secret"},
                yes=True,
            )

        assert "top-secret" not in caught.value.message

    def test_preserves_a_safe_planner_error(self, tmp_path: pathlib.Path) -> None:
        def plan(context: GenerationContext) -> ChangePlan:
            raise click.UsageError("safe input error")

        with pytest.raises(click.UsageError, match="safe input error"):
            run_generation(plan, target_root=tmp_path, yes=True)

    def test_hides_a_planner_click_error_when_answers_are_secret(self, tmp_path: pathlib.Path) -> None:
        def plan(context: GenerationContext) -> ChangePlan:
            raise click.UsageError(str(context.answers["token"]))

        with pytest.raises(click.ClickException) as caught:
            run_generation(
                plan,
                target_root=tmp_path,
                questions=(Question("token", "Token", secret=True),),
                answers={"token": "top-secret"},
                yes=True,
            )

        assert "top-secret" not in caught.value.message

    def test_redacts_secret_values_from_default_output(
        self, tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        report = run_generation(
            lambda context: ChangePlan((CreateFile(f"{context.answers['token']}.txt", "content", sensitive=True),)),
            target_root=tmp_path,
            questions=(Question("token", "Token", secret=True),),
            answers={"token": "top-secret"},
            yes=True,
            dry_run=True,
        )

        output = capsys.readouterr()
        assert "top-secret" not in output.out
        assert "***.txt" in output.out
        assert report.operations[0].path == pathlib.PurePath("***.txt")

    def test_redacts_secrets_before_custom_reporting(self, tmp_path: pathlib.Path) -> None:
        reporter = RecordingReporter()
        run_generation(
            lambda context: ChangePlan((CreateFile(f"{context.answers['token']}.txt", str(context.answers["token"])),)),
            target_root=tmp_path,
            questions=(
                Question("prefix", "Prefix", secret=True),
                Question("token", "Token", secret=True),
            ),
            answers={"prefix": "secret", "token": "top-secret\nsecond"},
            reporter=reporter,
            yes=True,
            dry_run=True,
        )

        operation = reporter.previews[0].operations[0]
        assert operation.relative_path == pathlib.PurePath("***.txt")
        assert operation.after == b"***"

    def test_redacts_secret_values_from_text_diffs(
        self, tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        run_generation(
            lambda context: ChangePlan((CreateFile("item.txt", str(context.answers["token"])),)),
            target_root=tmp_path,
            questions=(Question("token", "Token", secret=True),),
            answers={"token": "top-secret\nsecond"},
            yes=True,
            dry_run=True,
            show_diff=True,
        )

        output = capsys.readouterr().out
        assert "top-secret" not in output
        assert "second" not in output

    def test_hides_file_modifier_exception_details(self, tmp_path: pathlib.Path) -> None:
        @dataclasses.dataclass(frozen=True)
        class BrokenModification:
            path: str = "item.txt"
            before: str = "before"
            mode: int | None = None
            sensitive: bool = True

            def render(self, content: bytes) -> bytes:
                raise RuntimeError("top-secret")

        (tmp_path / "item.txt").write_text("before")

        with pytest.raises(click.ClickException) as caught:
            run_generation(
                lambda context: ChangePlan((BrokenModification(),)),
                target_root=tmp_path,
                yes=True,
            )

        assert "top-secret" not in caught.value.message

    def test_hides_application_exception_details(self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            runtime,
            "apply_plan",
            lambda plan: (_ for _ in ()).throw(OSError("secret filesystem detail")),
        )

        with pytest.raises(click.ClickException) as caught:
            run_generation(
                lambda context: ChangePlan((CreateFile("item.txt", "content"),)),
                target_root=tmp_path,
                yes=True,
            )

        assert "secret filesystem detail" not in caught.value.message

    def test_preserves_a_safe_application_conflict(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            runtime,
            "apply_plan",
            lambda plan: (_ for _ in ()).throw(ConflictError("safe conflict")),
        )

        with pytest.raises(ConflictError, match="safe conflict"):
            run_generation(
                lambda context: ChangePlan((CreateFile("item.txt", "content"),)),
                target_root=tmp_path,
                yes=True,
            )

    def test_hides_a_secret_application_conflict(self, tmp_path: pathlib.Path) -> None:
        class ConcurrentWriter(RecordingReporter):
            def preview(self, plan: PreparedPlan) -> None:
                super().preview(plan)
                (tmp_path / "top-secret.txt").write_text("concurrent")

        reporter = ConcurrentWriter()

        with pytest.raises(click.UsageError) as caught:
            run_generation(
                lambda context: ChangePlan((CreateFile(f"{context.answers['token']}.txt", "content"),)),
                target_root=tmp_path,
                questions=(Question("token", "Token", secret=True),),
                answers={"token": "top-secret"},
                yes=True,
                reporter=reporter,
            )

        assert "top-secret" not in caught.value.message
        assert reporter.reports[0].operations[0].status is OperationStatus.CONFLICTED
        assert reporter.reports[0].operations[0].path == pathlib.PurePath("***.txt")

    def test_reports_a_preflight_conflict(self, tmp_path: pathlib.Path) -> None:
        (tmp_path / "item.txt").write_text("existing")
        reporter = RecordingReporter()

        with pytest.raises(ConflictError):
            run_generation(
                lambda context: ChangePlan((CreateFile("item.txt", "different"),)),
                target_root=tmp_path,
                yes=True,
                reporter=reporter,
            )

        report = reporter.reports[0]
        assert report.operations[0].status is OperationStatus.CONFLICTED
        assert report.operations[0].path == pathlib.PurePath("item.txt")

    def test_hides_a_secret_preflight_conflict(
        self, tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        (tmp_path / "top-secret.txt").write_text("existing")

        with pytest.raises(click.UsageError) as caught:
            run_generation(
                lambda context: ChangePlan((CreateFile(f"{context.answers['token']}.txt", "different"),)),
                target_root=tmp_path,
                questions=(Question("token", "Token", secret=True),),
                answers={"token": "top-secret"},
                yes=True,
            )

        assert "top-secret" not in caught.value.message
        assert "top-secret" not in capsys.readouterr().err

    def test_reports_an_application_failure_before_raising(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        report = run_generation_report(OperationStatus.ROLLED_BACK, OperationStatus.FAILED)
        error = ApplyError(OSError("detail"), report)
        error.add_note("Backup preserved as .item.txt.backup.")

        def fail(plan: object) -> object:
            raise error

        monkeypatch.setattr(runtime, "apply_plan", fail)
        reporter = RecordingReporter()

        with pytest.raises(click.ClickException, match="Backup preserved"):
            run_generation(
                lambda context: ChangePlan((CreateFile("item.txt", "content"),)),
                target_root=tmp_path,
                yes=True,
                reporter=reporter,
            )

        assert reporter.reports == [report]


class TestClickReporter:
    def test_hides_diffs_by_default(self, tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]) -> None:
        prepared = prepare_plan(ChangePlan((CreateFile("text.txt", "hello"),)), tmp_path)

        ClickReporter().preview(prepared)
        output = capsys.readouterr().out

        assert "created" in output
        assert "text.txt" in output
        assert "+hello" not in output

    def test_colors_actions(self, tmp_path: pathlib.Path) -> None:
        prepared = prepare_plan(ChangePlan((CreateFile("text.txt", "hello"),)), tmp_path)

        @click.command()
        def command() -> None:
            ClickReporter().preview(prepared)

        result = CliRunner().invoke(command, color=True)

        assert result.output == f"{click.style('created  ', fg='green')} text.txt\n"

    def test_reports_diffs_when_requested(self, tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]) -> None:
        reporter = ClickReporter(show_diff=True)
        prepared = prepare_plan(
            ChangePlan(
                (
                    CreateFile("text.txt", "hello"),
                    CreateFile("binary.bin", b"\xff"),
                    CreateFile("secret.txt", "do-not-print", sensitive=True),
                    CreateDirectory("pkg"),
                )
            ),
            tmp_path,
        )

        reporter.preview(prepared)
        output = capsys.readouterr().out

        assert "+hello" in output
        assert "binary 0 -> 1 bytes" in output
        assert "secret.txt" in output
        assert "do-not-print" not in output
        assert "pkg" in output

    def test_uses_the_configured_confirmation_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        seen: list[tuple[str, bool]] = []

        def confirm(prompt: str, *, default: bool) -> bool:
            seen.append((prompt, default))
            return True

        monkeypatch.setattr(click, "confirm", confirm)

        assert ClickReporter().confirm()
        assert ClickReporter(confirm_default=True).confirm()
        assert seen == [("Apply these changes?", False), ("Apply these changes?", True)]

    def test_reports_singular_and_plural_completion(self, capsys: pytest.CaptureFixture[str]) -> None:
        reporter = ClickReporter()
        reporter.finish(run_generation_report(OperationStatus.CREATED))
        reporter.finish(run_generation_report(OperationStatus.CREATED, OperationStatus.MODIFIED))

        assert capsys.readouterr().out == "Applied 1 change.\nApplied 2 changes.\n"

    def test_reports_failure_statuses_to_stderr(self, capsys: pytest.CaptureFixture[str]) -> None:
        ClickReporter().finish(
            run_generation_report(OperationStatus.CONFLICTED, OperationStatus.ROLLED_BACK, OperationStatus.FAILED)
        )

        output = capsys.readouterr().err
        assert "conflicted" in output
        assert "rolled-back" in output
        assert "failed" in output


def run_generation_report(*statuses: OperationStatus) -> GenerationReport:
    return GenerationReport(
        tuple(OperationResult(pathlib.PurePath(f"{index}.txt"), status) for index, status in enumerate(statuses))
    )


class TestGenerator:
    def test_keeps_an_ordinary_click_command_and_uses_explicit_values(self, tmp_path: pathlib.Path) -> None:
        seen: list[tuple[GenerationContext, str]] = []

        @generator(questions=(Question("name", "Name", default="question-default"),))
        @click.command()
        @click.option("--name", default="click-default")
        def widget(context: GenerationContext, name: str) -> ChangePlan:
            seen.append((context, name))
            return ChangePlan((CreateFile("item.txt", name),))

        assert isinstance(widget, click.Command)
        result = CliRunner().invoke(
            widget,
            ["--project", str(tmp_path), "--name", "click-default", "--yes"],
        )

        assert result.exit_code == 0
        assert (tmp_path / "item.txt").read_text() == "click-default"
        assert seen[0][1] == seen[0][0].answers["name"]
        assert seen[0][0].workspace_root is None

    def test_uses_the_workspace_member_as_the_project_root(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        workspace = tmp_path / "workspace"
        project = workspace / "src"
        nested = project / "package"
        nested.mkdir(parents=True)
        (workspace / "pyproject.toml").write_text('[tool.uv.workspace]\nmembers = ["src"]\n')
        (project / "pyproject.toml").write_text('[project]\nname = "project"\nversion = "0.1.0"\n')
        seen: list[GenerationContext] = []

        @generator()
        @click.command()
        def widget(context: GenerationContext) -> ChangePlan:
            seen.append(context)
            return ChangePlan((CreateFile("item.txt", "content"),))

        runner = CliRunner()
        root_result = runner.invoke(widget, ["--project", str(workspace), "--yes"])
        monkeypatch.chdir(nested)
        nested_result = runner.invoke(widget, ["--yes"])

        assert root_result.exit_code == 0
        assert nested_result.exit_code == 0
        assert (project / "item.txt").read_text() == "content"
        assert [context.target_root for context in seen] == [project, project]
        assert [context.workspace_root for context in seen] == [workspace, workspace]

    def test_ignores_an_unrelated_uv_workspace(self, tmp_path: pathlib.Path) -> None:
        (tmp_path / "pyproject.toml").write_text('[tool.uv.workspace]\nmembers = ["packages/*"]\n')
        seen: list[GenerationContext] = []

        @generator()
        @click.command()
        def widget(context: GenerationContext) -> ChangePlan:
            seen.append(context)
            return ChangePlan(())

        result = CliRunner().invoke(widget, ["--project", str(tmp_path), "--yes"])

        assert result.exit_code == 0
        assert seen[0].target_root == tmp_path
        assert seen[0].workspace_root is None

    def test_ignores_a_click_default_for_an_interviewed_parameter(self, tmp_path: pathlib.Path) -> None:
        @generator(questions=(Question("name", "Name", default="question-default"),))
        @click.command()
        @click.option("--name", default="click-default")
        def widget(context: GenerationContext, name: str) -> ChangePlan:
            return ChangePlan((CreateFile("item.txt", name),))

        result = CliRunner().invoke(widget, ["--project", str(tmp_path), "--yes"])

        assert result.exit_code == 0
        assert (tmp_path / "item.txt").read_text() == "question-default"

    def test_derives_the_question_type_default_and_cli_hint(self, tmp_path: pathlib.Path) -> None:
        @generator(questions=(Question("count", "Count"),))
        @click.command()
        @click.option("--count", type=int, default=2)
        def widget(context: GenerationContext, count: int) -> ChangePlan:
            return ChangePlan((CreateFile("count.txt", str(count)),))

        result = CliRunner().invoke(widget, ["--project", str(tmp_path), "--yes"])

        assert result.exit_code == 0
        assert (tmp_path / "count.txt").read_text() == "2"

    def test_uses_a_callable_click_default(self, tmp_path: pathlib.Path) -> None:
        @generator(questions=(Question("name", "Name"),))
        @click.command()
        @click.option("--name", default=lambda: "widget")
        def widget(context: GenerationContext, name: str) -> ChangePlan:
            return ChangePlan((CreateFile("name.txt", name),))

        result = CliRunner().invoke(widget, ["--project", str(tmp_path), "--yes"])

        assert result.exit_code == 0
        assert (tmp_path / "name.txt").read_text() == "widget"

        required = Question[str]("name", "Name")

        @generator(questions=(required,))
        @click.command()
        @click.option("--name")
        def missing(context: GenerationContext, name: str | None) -> ChangePlan:
            return ChangePlan(())  # pragma: no cover - required answer validation stops first

        result = CliRunner().invoke(missing, ["--project", str(tmp_path), "--yes"])
        assert result.exit_code == 2
        assert "name (--name)" in result.output

    def test_preserves_unbound_click_parameters(self, tmp_path: pathlib.Path) -> None:
        @generator()
        @click.command()
        @click.option("--suffix", default="txt")
        def widget(context: GenerationContext, suffix: str) -> ChangePlan:
            return ChangePlan((CreateFile(f"item.{suffix}", "content"),))

        result = CliRunner().invoke(widget, ["--project", str(tmp_path), "--suffix", "md", "--yes"])

        assert result.exit_code == 0
        assert (tmp_path / "item.md").exists()

    def test_keeps_unbound_questions_in_the_generation_context(self, tmp_path: pathlib.Path) -> None:
        @generator(questions=(Question("module", "Module", default="billing"),))
        @click.command()
        def widget(context: GenerationContext) -> ChangePlan:
            return ChangePlan((CreateFile(f"{context.answers['module']}.py", "content"),))

        result = CliRunner().invoke(widget, ["--project", str(tmp_path), "--yes"])

        assert result.exit_code == 0
        assert (tmp_path / "billing.py").exists()

    def test_rejects_non_string_click_conversion_for_a_secret(self) -> None:
        command = click.Command(
            "widget",
            params=[click.Option(("--token",), type=int)],
            callback=lambda **kwargs: ChangePlan(()),
        )

        with pytest.raises(TypeError, match="secret"):
            generator(questions=(Question("token", "Token", secret=True),))(command)

        argument = click.Command(
            "widget",
            params=[click.Argument(("token",), required=False, type=int)],
            callback=lambda **kwargs: ChangePlan(()),
        )
        with pytest.raises(TypeError, match="secret"):
            generator(questions=(Question("token", "Token", secret=True),))(argument)

    def test_rejects_incompatible_click_and_question_types(self) -> None:
        command = click.Command(
            "widget",
            params=[click.Option(("--count",), type=int)],
            callback=lambda **kwargs: ChangePlan(()),
        )

        with pytest.raises(TypeError, match="incompatible"):
            generator(questions=(Question("count", "Count", type=float),))(command)

        choices = click.Command(
            "widget",
            params=[click.Option(("--kind",), type=click.Choice(("one", "two")))],
            callback=lambda **kwargs: ChangePlan(()),
        )
        with pytest.raises(TypeError, match="choices"):
            generator(questions=(Question("kind", "Kind", choices=("one", "three")),))(choices)

        compatible = click.Command(
            "widget",
            params=[click.Option(("--kind",), type=click.Choice(("one", "two")))],
            callback=lambda **kwargs: ChangePlan(()),
        )
        assert generator(questions=(Question("kind", "Kind", choices=("one", "two")),))(compatible) is compatible

        derived = click.Command(
            "widget",
            params=[click.Option(("--kind",), type=click.Choice(("one", "two")))],
            callback=lambda **kwargs: ChangePlan(()),
        )
        assert generator(questions=(Question("kind", "Kind"),))(derived) is derived

    def test_rejects_multiple_interviewed_values(self) -> None:
        command = click.Command(
            "widget",
            params=[click.Option(("--name",), multiple=True)],
            callback=lambda **kwargs: ChangePlan(()),
        )

        with pytest.raises(TypeError, match="single value"):
            generator(questions=(Question("name", "Name"),))(command)

    def test_supports_an_explicit_question_binding(self, tmp_path: pathlib.Path) -> None:
        @generator(questions=(Question("widget_name", "Name"),), bindings={"widget_name": "name"})
        @click.command()
        @click.option("--name")
        def widget(context: GenerationContext, name: str) -> ChangePlan:
            return ChangePlan((CreateFile(f"{name}.txt", "content"),))

        result = CliRunner().invoke(
            widget,
            ["--project", str(tmp_path), "--name", "bound", "--yes"],
        )

        assert result.exit_code == 0
        assert (tmp_path / "bound.txt").exists()

    def test_preserves_explicit_question_metadata(self, tmp_path: pathlib.Path) -> None:
        @generator(questions=(Question("count", "Count", type=int, default=3, cli_hint="COUNT"),))
        @click.command()
        @click.option("--count", type=int, default=2)
        def widget(context: GenerationContext, count: int) -> ChangePlan:
            return ChangePlan((CreateFile("count.txt", str(count)),))

        result = CliRunner().invoke(widget, ["--project", str(tmp_path), "--yes"])

        assert result.exit_code == 0
        assert (tmp_path / "count.txt").read_text() == "3"

    def test_preserves_bound_click_type_constraints(self, tmp_path: pathlib.Path) -> None:
        @generator(questions=(Question("count", "Count", type=int, default=9),))
        @click.command()
        @click.option("--count", type=click.IntRange(1, 3))
        def widget(context: GenerationContext, count: int) -> ChangePlan:
            return ChangePlan(())  # pragma: no cover - range validation stops first

        result = CliRunner().invoke(widget, ["--project", str(tmp_path), "--yes"])

        assert result.exit_code == 2
        assert "not in the range 1<=x<=3" in result.output

    def test_preserves_explicit_question_type_constraints(self, tmp_path: pathlib.Path) -> None:
        @generator(questions=(Question("count", "Count", type=click.IntRange(1, 3)),))
        @click.command()
        @click.option("--count", type=click.IntRange(1, 9))
        def widget(context: GenerationContext, count: int) -> ChangePlan:
            return ChangePlan(())  # pragma: no cover - range validation stops first

        result = CliRunner().invoke(widget, ["--project", str(tmp_path), "--count", "4", "--yes"])

        assert result.exit_code == 2
        assert "not in the range 1<=x<=3" in result.output

    def test_allows_an_optional_unanswered_binding(self, tmp_path: pathlib.Path) -> None:
        @generator(questions=(Question("name", "Name", required=False),))
        @click.command()
        @click.option("--name")
        def widget(context: GenerationContext, name: str | None) -> ChangePlan:
            assert name is None
            return ChangePlan(())

        result = CliRunner().invoke(widget, ["--project", str(tmp_path), "--yes"])

        assert result.exit_code == 0

    def test_allows_an_optional_click_argument_binding(self) -> None:
        command = click.Command(
            "widget",
            params=[click.Argument(("name",), required=False)],
            callback=lambda context, **kwargs: ChangePlan(()),
        )

        assert generator(questions=(Question("name", "Name", required=False),))(command) is command

    @pytest.mark.parametrize(
        ("parameter", "message"),
        [
            (click.Option(("--name",), required=True), "required"),
            (click.Option(("--name",), prompt=True), "prompt"),
            (click.Option(("--name",), expose_value=False), "expose"),
            (click.Option(("--name",), callback=lambda ctx, parameter, value: value), "callback"),
        ],
    )
    def test_rejects_click_prompting_and_required_interviewed_options(
        self, parameter: click.Option, message: str
    ) -> None:
        command = click.Command("widget", params=[parameter], callback=lambda **kwargs: ChangePlan(()))

        with pytest.raises(TypeError, match=message):
            generator(questions=(Question("name", "Name"),))(command)

    def test_rejects_unknown_bindings(self) -> None:
        command = click.Command("widget", callback=lambda: ChangePlan(()))

        with pytest.raises(TypeError, match="unknown Click parameter"):
            generator(questions=(Question("name", "Name"),), bindings={"name": "other"})(command)

        with pytest.raises(TypeError, match="unknown question"):
            generator(bindings={"missing": "name"})(command)

    def test_rejects_duplicate_parameter_bindings(self) -> None:
        command = click.Command(
            "widget",
            params=[click.Option(("--name",))],
            callback=lambda **kwargs: ChangePlan(()),
        )

        with pytest.raises(TypeError, match="more than one question"):
            generator(
                questions=(Question("first", "First"), Question("second", "Second")),
                bindings={"first": "name", "second": "name"},
            )(command)

    def test_rejects_common_option_collisions(self) -> None:
        command = click.Command("widget", params=[click.Option(("--yes",))], callback=lambda: ChangePlan(()))

        with pytest.raises(TypeError, match="reserved option"):
            generator()(command)

        aliased = click.Command(
            "widget",
            params=[click.Option(("--yes", "approve"))],
            callback=lambda: ChangePlan(()),
        )
        with pytest.raises(TypeError, match="reserved option"):
            generator()(aliased)

    def test_rejects_a_command_without_a_callback(self) -> None:
        with pytest.raises(TypeError, match="callback"):
            generator()(click.Command("widget"))

    def test_rejects_a_callback_result_that_is_not_a_plan(self, tmp_path: pathlib.Path) -> None:
        @generator()
        @click.command()
        def widget(context: GenerationContext) -> None:
            pass

        result = CliRunner().invoke(widget, ["--project", str(tmp_path), "--yes"])

        assert result.exit_code == 1
        assert "Generation planning failed" in result.output

    def test_rejects_a_required_click_argument(self) -> None:
        command = click.Command(
            "widget",
            params=[click.Argument(("name",), required=True)],
            callback=lambda **kwargs: ChangePlan(()),
        )

        with pytest.raises(TypeError, match="required"):
            generator(questions=(Question("name", "Name"),))(command)

    def test_rejects_environment_values_for_bound_questions(self, tmp_path: pathlib.Path) -> None:
        @generator(questions=(Question("name", "Name", default="safe"),))
        @click.command()
        @click.option("--name", envvar="WIDGET_NAME")
        def widget(context: GenerationContext, name: str) -> ChangePlan:
            return ChangePlan((CreateFile("item.txt", name),))  # pragma: no cover - source is rejected

        result = CliRunner().invoke(
            widget,
            ["--project", str(tmp_path), "--yes"],
            env={"WIDGET_NAME": "environment"},
        )

        assert result.exit_code == 2
        assert "environment or default-map" in result.output

    def test_rejects_default_map_values_for_bound_questions(self, tmp_path: pathlib.Path) -> None:
        @generator(questions=(Question("name", "Name", default="safe"),))
        @click.command()
        @click.option("--name")
        def widget(context: GenerationContext, name: str) -> ChangePlan:
            return ChangePlan((CreateFile("item.txt", name),))  # pragma: no cover - source is rejected

        result = CliRunner().invoke(
            widget,
            ["--project", str(tmp_path), "--yes"],
            default_map={"name": "mapped"},
        )

        assert result.exit_code == 2
        assert "environment or default-map" in result.output

    def test_exposes_the_common_options_in_help(self) -> None:
        @generator()
        @click.command()
        def widget(context: GenerationContext) -> ChangePlan:
            return ChangePlan(())  # pragma: no cover - help does not invoke the command

        result = CliRunner().invoke(widget, ["--help"])

        assert result.exit_code == 0
        for option in ("--project", "--yes", "--dry-run", "--diff", "--force"):
            assert option in result.output
