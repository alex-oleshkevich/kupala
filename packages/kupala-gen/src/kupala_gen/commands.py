import contextlib
import dataclasses
import keyword
import pathlib
import typing

import click
from packaging.utils import InvalidName, canonicalize_name

from kupala.commands import BootstrapCommand, Commands
from kupala_gen.loading import GeneratorGroup
from kupala_gen.plans import ChangeOperation, ChangePlan, CreateDirectory
from kupala_gen.runtime import ClickReporter, GenerationContext, run_generation
from kupala_gen.sources import (
    BundledTemplate,
    FileTemplate,
    GitTemplate,
    TemplateIdentity,
    TemplateSnapshot,
    TemplateSource,
    resolve_template,
)
from kupala_gen.templates import inspect_template, render_template

_BUNDLED_TEMPLATES = frozenset({"minimal", "standard", "api"})


def _parse_answers(values: tuple[str, ...], option: str) -> dict[str, str]:
    answers: dict[str, str] = {}
    for value in values:
        key, separator, answer = value.partition("=")
        if not separator or not key:
            raise click.UsageError(f"{option} must use KEY=VALUE.")

        if key in answers:
            raise click.UsageError(f"Duplicate answer: {key}")

        answers[key] = answer

    return answers


@contextlib.contextmanager
def _resolve_source(
    source: TemplateSource,
    *,
    trust: bool,
    confirm: typing.Callable[[TemplateIdentity], bool] | None,
) -> typing.Iterator[TemplateSnapshot]:
    try:
        with resolve_template(source, trust=trust, confirm=confirm) as snapshot:
            yield snapshot
    except (FileNotFoundError, PermissionError, ValueError) as error:
        raise click.UsageError(str(error)) from None


def _build_new_command(command_class: type[click.Command] = click.Command) -> click.Command:
    def validate_project(value: str) -> bool | str:
        try:
            canonicalize_name(value, validate=True)
        except InvalidName:
            return "must be a valid project name"

        return True

    def validate_package(value: object) -> bool | str:
        if isinstance(value, str) and value.isidentifier() and not keyword.iskeyword(value):
            return True

        return "must be a Python package name"

    @click.command("new", cls=command_class)
    @click.argument(
        "destination",
        type=click.Path(path_type=pathlib.Path, file_okay=False),
        default=pathlib.Path("."),
    )
    @click.option(
        "--template",
        default="standard",
        show_default=True,
        help="Bundled template name, HTTPS Git URL, or absolute file URI.",
    )
    @click.option("--ref", "revision", help="Git revision for a remote template.")
    @click.option("--trust-template", is_flag=True, help="Trust a custom template.")
    @click.option("--answer", multiple=True, metavar="KEY=VALUE", help="Answer a custom template question.")
    @click.option("--name", help="Project name.")
    @click.option("--package", "package_name", help="Python package name.")
    @click.option("--workspace", is_flag=True, help="Create a uv workspace with the project in src.")
    @click.option(
        "--force",
        is_flag=True,
        help="Use an existing destination and overwrite files the template allows replacing.",
    )
    @click.option("--diff", "show_diff", is_flag=True, help="Show file diffs.")
    @click.option("--dry-run", is_flag=True, help="Preview changes without writing.")
    @click.option("--yes", is_flag=True, help="Apply without prompting.")
    def new(
        destination: pathlib.Path,
        template: str,
        revision: str | None,
        trust_template: bool,
        answer: tuple[str, ...],
        name: str | None,
        package_name: str | None,
        workspace: bool,
        force: bool,
        show_diff: bool,
        dry_run: bool,
        yes: bool,
    ) -> None:
        """Create a new project in DESTINATION."""

        if destination.exists() and not force:
            raise click.UsageError(f"Destination already exists: {destination}")

        target = destination.resolve()
        direct_answers = _parse_answers(answer, "--answer")
        bundled = template in _BUNDLED_TEMPLATES
        project_name = name or target.name
        supplied_package = package_name
        package_name = package_name or project_name.replace("-", "_")
        if revision is not None and (bundled or template.startswith("file:")):
            raise click.UsageError("--ref is only valid for Git templates.")

        source: TemplateSource
        if bundled:
            source = BundledTemplate("kupala_gen", f"project_templates/{template}")
        elif template.startswith("file:"):
            source = FileTemplate(template)
        else:
            source = GitTemplate(template, revision or "HEAD")

        def confirm(identity: TemplateIdentity) -> bool:
            return click.confirm(f"Trust template {identity.source} at {identity.resolved}?")

        confirmation = None if yes or trust_template else confirm

        with _resolve_source(source, trust=trust_template, confirm=confirmation) as snapshot:
            definition = inspect_template(snapshot)
            defaults = {"name": project_name, "package": package_name} if bundled else {}
            questions = tuple(
                dataclasses.replace(
                    question,
                    default=defaults[question.key],
                    validate=validate_project if question.key == "name" else validate_package,
                )
                if question.key in defaults
                else question
                for question in definition.questions
            )
            question_keys = {question.key for question in questions}
            supplied: dict[str, object] = dict(direct_answers)
            for key, value in {"name": name, "package": supplied_package}.items():
                if value is not None and key in question_keys:
                    if key in supplied:
                        raise click.UsageError(f"Duplicate answer: {key}")

                    supplied[key] = value

            workspace_operations: tuple[ChangeOperation, ...] = ()
            if workspace:
                workspace_source = BundledTemplate("kupala_gen", "project_templates/workspace")
                with _resolve_source(workspace_source, trust=False, confirm=None) as workspace_snapshot:
                    workspace_operations = render_template(
                        inspect_template(workspace_snapshot),
                        {"name": f"{project_name}-workspace"},
                    ).operations

            def plan(context: GenerationContext) -> ChangePlan:
                rendered = render_template(definition, context.answers)
                directory = pathlib.PurePath(target.name)
                project_directory = directory
                operations: list[ChangeOperation] = [CreateDirectory(directory)]
                if workspace:
                    project_directory /= "src"
                    operations.extend(
                        dataclasses.replace(typing.cast(typing.Any, operation), path=directory / operation.path)
                        for operation in workspace_operations
                    )
                    operations.append(CreateDirectory(project_directory))

                operations.extend(
                    dataclasses.replace(typing.cast(typing.Any, operation), path=project_directory / operation.path)
                    for operation in rendered.operations
                )
                return ChangePlan(tuple(operations))

            run_generation(
                plan,
                target_root=target.parent,
                questions=questions,
                answers=supplied,
                yes=yes,
                dry_run=dry_run,
                force=force,
                reporter=ClickReporter(show_diff=show_diff, confirm_default=True),
                workspace_root=target if workspace else None,
            )

    return new


def build_gen_command(commands: Commands) -> click.Group:
    """Build a fresh generator command tree."""

    @commands.group("gen")
    def gen() -> None:
        """Generate code."""

    gen.add_command(_build_new_command())
    commands.bootstrap(typing.cast(BootstrapCommand, _build_new_command(BootstrapCommand)))

    @gen.group("add", cls=GeneratorGroup)
    def add() -> None:
        """Add a feature to the current project."""

    return gen
