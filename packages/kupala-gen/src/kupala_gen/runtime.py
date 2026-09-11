import dataclasses
import difflib
import functools
import hashlib
import pathlib
import sys
import typing

import click
from click.core import ParameterSource

from kupala_gen.plans import (
    ApplyError,
    ChangePlan,
    ConflictError,
    GenerationReport,
    OperationResult,
    OperationStatus,
    PreparedOperation,
    PreparedPlan,
    apply_plan,
    prepare_plan,
)
from kupala_gen.questions import UNSET, Ask, InteractionMode, Question, resolve_answers


def _redact(value: object, secrets: typing.Iterable[object]) -> str:
    text = str(value)
    for secret in filter(None, map(str, secrets)):
        text = text.replace(secret, "***")
    return text


class ProjectMetadata(typing.Protocol):
    root: pathlib.Path


class TemplateRenderer(typing.Protocol):
    def render(self, template: str, context: typing.Mapping[str, object]) -> bytes: ...


class CodemodRunner(typing.Protocol):
    def run(self, path: pathlib.Path, transform: object) -> bytes: ...


class Reporter(typing.Protocol):
    def preview(self, plan: PreparedPlan) -> None: ...

    def confirm(self) -> bool: ...

    def finish(self, report: GenerationReport) -> None: ...


class ClickReporter:
    def __init__(self, secrets: typing.Iterable[object] = ()) -> None:
        self._secrets = tuple(sorted(filter(None, map(str, secrets)), key=len, reverse=True))

    def _redact(self, value: object) -> str:
        return _redact(value, self._secrets)

    def preview(self, plan: PreparedPlan) -> None:
        for operation in plan.operations:
            click.echo(f"{operation.status.value:9} {self._redact(operation.relative_path)}")
            if operation.status is not OperationStatus.UNCHANGED and not operation.directory:
                self._diff(operation)

    def _diff(self, operation: PreparedOperation) -> None:
        if operation.sensitive:
            return
        before = operation.before or b""
        after = typing.cast(bytes, operation.after)
        try:
            before_text = before.decode()
            after_text = after.decode()
        except UnicodeDecodeError:
            click.echo(f"  binary {len(before)} -> {len(after)} bytes ({hashlib.sha256(after).hexdigest()})")
            return
        for line in difflib.unified_diff(
            before_text.splitlines(),
            after_text.splitlines(),
            fromfile=f"a/{self._redact(operation.relative_path)}",
            tofile=f"b/{self._redact(operation.relative_path)}",
            lineterm="",
        ):
            click.echo(self._redact(line))

    def confirm(self) -> bool:
        return click.confirm("Apply these changes?", default=False)

    def finish(self, report: GenerationReport) -> None:
        failures = tuple(
            result
            for result in report.operations
            if result.status in {OperationStatus.CONFLICTED, OperationStatus.FAILED, OperationStatus.ROLLED_BACK}
        )
        if failures:
            for result in failures:
                click.echo(f"{result.status.value:9} {self._redact(result.path)}", err=True)
            return
        changed = sum(result.status is not OperationStatus.UNCHANGED for result in report.operations)
        click.echo(f"Applied {changed} change{'s' if changed != 1 else ''}.")


@dataclasses.dataclass(frozen=True, slots=True)
class GenerationContext:
    target_root: pathlib.Path
    answers: typing.Mapping[str, object]
    interaction: InteractionMode
    force: bool
    reporter: Reporter
    project: ProjectMetadata | None = None
    renderer: TemplateRenderer | None = None
    codemods: CodemodRunner | None = None


type Planner = typing.Callable[[GenerationContext], ChangePlan]


def _report(plan: PreparedPlan) -> GenerationReport:
    return GenerationReport(
        tuple(OperationResult(operation.relative_path, operation.status) for operation in plan.operations)
    )


def _redact_report(report: GenerationReport, secrets: typing.Iterable[object]) -> GenerationReport:
    return GenerationReport(
        tuple(
            OperationResult(pathlib.PurePath(_redact(result.path, secrets)), result.status)
            for result in report.operations
        )
    )


def run_generation(
    planner: Planner,
    *,
    target_root: pathlib.Path,
    questions: typing.Sequence[Question[typing.Any]] = (),
    answers: typing.Mapping[str, object] | None = None,
    yes: bool = False,
    dry_run: bool = False,
    force: bool = False,
    reporter: Reporter | None = None,
    interaction: InteractionMode | None = None,
    ask: Ask | None = None,
    project: ProjectMetadata | None = None,
    renderer: TemplateRenderer | None = None,
    codemods: CodemodRunner | None = None,
) -> GenerationReport:
    mode = (
        InteractionMode.ASSUME_YES
        if yes
        else interaction
        if interaction is not None
        else InteractionMode.INTERACTIVE
        if sys.stdin.isatty()
        else InteractionMode.NON_INTERACTIVE
    )
    resolved = resolve_answers(questions, answers or {}, mode=mode, ask=ask)
    secret_values = tuple(
        resolved[question.key] for question in questions if question.secret and question.key in resolved
    )
    output = reporter or ClickReporter(secret_values)
    context = GenerationContext(
        target_root=target_root.resolve(),
        answers=resolved,
        interaction=mode,
        force=force,
        reporter=output,
        project=project,
        renderer=renderer,
        codemods=codemods,
    )
    try:
        plan = planner(context)
    except click.ClickException:
        if secret_values:
            raise click.ClickException("Generation planning failed.") from None
        raise
    except Exception:  # noqa: BLE001 - planner errors may contain secret answers
        raise click.ClickException("Generation planning failed.") from None
    try:
        prepared = prepare_plan(plan, context.target_root, force=force)
    except ConflictError as error:
        output.finish(_redact_report(error.report, secret_values))
        if secret_values:
            raise click.UsageError("Generation plan conflicts with existing files.") from None
        raise
    except Exception:  # noqa: BLE001 - operation renderers may contain secret answers
        raise click.ClickException("Generation planning failed.") from None
    output.preview(prepared)
    preview = _redact_report(_report(prepared), secret_values)
    if dry_run:
        return preview

    changed = any(operation.status is not OperationStatus.UNCHANGED for operation in prepared.operations)
    if not changed:
        output.finish(preview)
        return preview
    if not yes:
        if mode is not InteractionMode.INTERACTIVE:
            raise click.UsageError("Applying changes requires --yes when input is not interactive.")
        if not output.confirm():
            raise click.Abort

    try:
        report = apply_plan(prepared)
    except ConflictError as error:
        output.finish(_redact_report(error.report, secret_values))
        if secret_values:
            raise click.UsageError("Generation plan conflicts with existing files.") from None
        raise
    except ApplyError as error:
        output.finish(_redact_report(error.report, secret_values))
        notes = "\n".join(getattr(error, "__notes__", ()))
        notes = _redact(notes, secret_values)
        message = "Could not apply the generation plan."
        raise click.ClickException(f"{message}\n{notes}" if notes else message) from None
    except Exception:  # noqa: BLE001 - filesystem errors may expose sensitive paths or content
        raise click.ClickException("Could not apply the generation plan.") from None
    safe_report = _redact_report(report, secret_values)
    output.finish(safe_report)
    return safe_report


_COMMON_OPTIONS = frozenset({"project", "yes", "dry_run", "force"})


def _bound_questions(
    command: click.Command,
    questions: typing.Sequence[Question[typing.Any]],
    bindings: typing.Mapping[str, str],
) -> tuple[
    tuple[Question[typing.Any], ...],
    tuple[tuple[Question[typing.Any], str], ...],
]:
    parameters = {parameter.name: parameter for parameter in command.params if parameter.name}
    unknown_questions = bindings.keys() - {question.key for question in questions}
    if unknown_questions:
        raise TypeError(f"Binding names unknown question: {min(unknown_questions)}")

    normalized: list[Question[typing.Any]] = []
    bound: list[tuple[Question[typing.Any], str]] = []
    bound_parameters: set[str] = set()
    for question in questions:
        parameter_name = bindings.get(question.key, question.key)
        parameter = parameters.get(parameter_name)
        if parameter is None:
            if question.key in bindings:
                raise TypeError(f"Binding names unknown Click parameter: {parameter_name}")
            normalized.append(question)
            continue
        if parameter_name in bound_parameters:
            raise TypeError(f"Click parameter cannot answer more than one question: {parameter_name}")
        bound_parameters.add(parameter_name)
        if parameter.required:
            raise TypeError(f"Interviewed Click parameter cannot be required: {parameter_name}")
        if not parameter.expose_value:
            raise TypeError(f"Interviewed Click parameter must expose its value: {parameter_name}")
        if parameter.callback is not None:
            raise TypeError(f"Interviewed Click parameter cannot use a Click callback: {parameter_name}")
        if parameter.nargs != 1 or (isinstance(parameter, click.Option) and parameter.multiple):
            raise TypeError(f"Interviewed Click parameter must produce one single value: {parameter_name}")
        if isinstance(parameter, click.Option) and parameter.prompt is not None:
            raise TypeError(f"Interviewed Click parameter cannot use a Click prompt: {parameter_name}")
        if question.secret and not isinstance(parameter.type, click.types.StringParamType):
            raise TypeError(f"A secret Click parameter must use string conversion: {parameter_name}")
        derived = question
        question_type = click.types.convert_type(question.type)
        if question.type is not str and not isinstance(parameter.type, type(question_type)):
            raise TypeError(f"Question and Click parameter types are incompatible: {parameter_name}")
        if isinstance(parameter.type, click.Choice):
            click_choices = tuple(parameter.type.choices)
            if question.choices and question.choices != click_choices:
                raise TypeError(f"Question and Click parameter choices are incompatible: {parameter_name}")
            if not question.choices:
                derived = dataclasses.replace(derived, choices=click_choices)
        derived = dataclasses.replace(derived, type=parameter.type)
        if isinstance(parameter, click.Option) and derived.cli_hint is None and parameter.opts:
            derived = dataclasses.replace(derived, cli_hint=parameter.opts[0])
        question = derived
        normalized.append(question)
        bound.append((question, parameter_name))
    return tuple(normalized), tuple(bound)


def generator(
    *,
    questions: typing.Sequence[Question[typing.Any]] = (),
    bindings: typing.Mapping[str, str] | None = None,
) -> typing.Callable[[click.Command], click.Command]:
    def decorate(command: click.Command) -> click.Command:
        names = {parameter.name for parameter in command.params if parameter.name}
        option_flags = {
            option
            for parameter in command.params
            if isinstance(parameter, click.Option)
            for option in (*parameter.opts, *parameter.secondary_opts)
        }
        collision = (names & _COMMON_OPTIONS) | {
            option.removeprefix("--").replace("-", "_")
            for option in option_flags
            if option in {"--project", "--yes", "--dry-run", "--force"}
        }
        if collision:
            raise TypeError(f"Generator command uses reserved option: {min(collision)}")
        callback = command.callback
        if callback is None:
            raise TypeError("Generator command needs a callback")
        normalized, bound = _bound_questions(command, questions, bindings or {})

        @functools.wraps(callback)
        @click.pass_context
        def invoke(ctx: click.Context, /, **kwargs: object) -> None:
            project = typing.cast(pathlib.Path, kwargs.pop("project"))
            yes = typing.cast(bool, kwargs.pop("yes"))
            dry_run = typing.cast(bool, kwargs.pop("dry_run"))
            force = typing.cast(bool, kwargs.pop("force"))
            explicit: dict[str, object] = {}
            defaults: dict[str, object] = {}
            for question, parameter_name in bound:
                source = ctx.get_parameter_source(parameter_name)
                if source in (ParameterSource.ENVIRONMENT, ParameterSource.DEFAULT_MAP):
                    raise click.UsageError(
                        f"Interviewed parameter {parameter_name} cannot come from environment or default-map input."
                    )
                if source is ParameterSource.COMMANDLINE:
                    explicit[question.key] = kwargs[parameter_name]
                elif (
                    source is ParameterSource.DEFAULT
                    and question.default is UNSET
                    and kwargs[parameter_name] is not None
                ):
                    defaults[question.key] = kwargs[parameter_name]

            runtime_questions = tuple(
                dataclasses.replace(question, default=defaults[question.key]) if question.key in defaults else question
                for question in normalized
            )

            def plan(context: GenerationContext) -> ChangePlan:
                arguments = kwargs.copy()
                for question, parameter_name in bound:
                    if question.key in context.answers:
                        arguments[parameter_name] = context.answers[question.key]
                result = callback(context, **arguments)
                if not isinstance(result, ChangePlan):
                    raise TypeError("Generator callback must return ChangePlan")
                return result

            run_generation(
                plan,
                target_root=project,
                questions=runtime_questions,
                answers=explicit,
                yes=yes,
                dry_run=dry_run,
                force=force,
            )

        command.callback = invoke
        click.option("--force", is_flag=True, help="Overwrite operations that explicitly allow it.")(command)
        click.option("--dry-run", is_flag=True, help="Preview changes without writing.")(command)
        click.option("--yes", is_flag=True, help="Apply without prompting.")(command)
        click.option(
            "--project",
            type=click.Path(path_type=pathlib.Path, file_okay=False, exists=True),
            default=pathlib.Path.cwd,
            show_default="current directory",
        )(command)
        return command

    return decorate
