import dataclasses
import os
import pathlib
import stat
import tempfile
import typing
import unicodedata

import copier
import jinja2
import yaml
from jinja2 import meta
from jinja2.sandbox import SandboxedEnvironment

from kupala_gen.plans import ChangePlan, CreateDirectory, CreateFile
from kupala_gen.questions import UNSET, InteractionMode, Question, resolve_answers
from kupala_gen.sources import TemplateSnapshot


@dataclasses.dataclass(frozen=True, slots=True)
class TemplateDefinition:
    snapshot: TemplateSnapshot
    questions: tuple[Question[typing.Any], ...]


_QUESTION_FIELDS = frozenset({"type", "default", "choices", "help", "question", "required", "secret", "when"})
_TYPES: dict[str, type[object]] = {"str": str, "bool": bool, "int": int, "float": float}


def _condition(value: object, earlier: set[str], key: str) -> typing.Callable[[typing.Mapping[str, object]], bool]:
    if not isinstance(value, str):
        raise TypeError(f"Condition for {key} must be a string.")
    expression = value.strip()
    if expression.startswith("{{") and expression.endswith("}}"):
        expression = expression[2:-2].strip()
    environment = SandboxedEnvironment(undefined=jinja2.StrictUndefined)
    variables = meta.find_undeclared_variables(environment.parse(f"{{{{ {expression} }}}}"))
    if not variables <= earlier:
        raise ValueError(f"Condition for {key} may reference only earlier questions.")
    compiled = environment.compile_expression(expression, undefined_to_none=False)

    def evaluate(answers: typing.Mapping[str, object]) -> bool:
        missing = variables - answers.keys()
        if missing:
            raise KeyError(min(missing))
        result = compiled(**answers)
        if not isinstance(result, bool):
            raise TypeError(f"Condition for {key} did not produce a boolean.")
        return result

    return evaluate


def _configuration(root: pathlib.Path) -> dict[str, object]:
    paths = [path for name in ("copier.yml", "copier.yaml") if (path := root / name).exists()]
    if len(paths) > 1:
        raise ValueError("Template contains more than one Copier configuration file.")
    if not paths:
        return {}
    try:
        documents = list(yaml.safe_load_all(paths[0].read_text()))
    except (OSError, UnicodeError, yaml.YAMLError) as error:
        raise ValueError("Could not read Copier configuration.") from error
    if len(documents) != 1 or not isinstance(documents[0], dict):
        raise ValueError("Copier configuration must contain one mapping.")
    return typing.cast(dict[str, object], documents[0])


def inspect_template(snapshot: TemplateSnapshot) -> TemplateDefinition:
    configuration = _configuration(snapshot.root)
    settings = {key for key in configuration if not isinstance(key, str) or key.startswith("_")}
    unsupported = settings - {"_secret_questions"}
    if unsupported:
        raise ValueError(f"Unsupported Copier setting: {min(map(str, unsupported))}")
    secrets = configuration.pop("_secret_questions", [])
    if not isinstance(secrets, list) or not all(isinstance(key, str) for key in secrets):
        raise ValueError("_secret_questions must be a list of question names.")

    questions: list[Question[typing.Any]] = []
    earlier: set[str] = set()
    for key, raw in configuration.items():
        if not isinstance(key, str) or not key or key.startswith("_"):
            raise ValueError("Question names must be non-empty strings.")
        if raw is None:
            values: dict[str, object] = {}
        elif isinstance(raw, dict):
            if not all(isinstance(name, str) for name in raw):
                raise ValueError(f"Unsupported metadata for {key}.")
            values = typing.cast(dict[str, object], raw.copy())
        else:
            values = {"default": raw, "type": type(raw).__name__}
        unknown = values.keys() - _QUESTION_FIELDS
        if unknown:
            raise ValueError(f"Unsupported metadata for {key}: {min(unknown)}")
        type_name = values.pop("type", "str")
        if not isinstance(type_name, str) or type_name not in _TYPES:
            raise ValueError(f"Unsupported question type for {key}: {type_name}")
        choices = values.pop("choices", [])
        if not isinstance(choices, list):
            raise TypeError(f"Choices for {key} must be a list.")
        default = values.pop("default", UNSET)
        required = values.pop("required", default is UNSET)
        if not isinstance(required, bool):
            raise TypeError(f"Requiredness for {key} must be a boolean.")
        secret = values.pop("secret", key in secrets)
        if not isinstance(secret, bool):
            raise TypeError(f"Secrecy for {key} must be a boolean.")
        prompt = values.pop("question", values.pop("help", key))
        if not isinstance(prompt, str):
            raise TypeError(f"Prompt for {key} must be a string.")
        when_value = values.pop("when", None)
        when = _condition(when_value, earlier, key) if when_value is not None else None
        questions.append(
            Question(
                key,
                prompt,
                type=_TYPES[type_name],
                default=default,
                required=required,
                choices=tuple(choices),
                secret=secret,
                when=when,
            )
        )
        earlier.add(key)
    unknown_secrets = set(secrets) - earlier
    if unknown_secrets:
        raise ValueError(f"Unknown secret question: {min(unknown_secrets)}")
    return TemplateDefinition(snapshot, tuple(questions))


def _rendered_paths(definition: TemplateDefinition, answers: typing.Mapping[str, object]) -> None:
    environment = SandboxedEnvironment(undefined=jinja2.StrictUndefined)
    destinations: dict[tuple[str, ...], tuple[pathlib.PurePath, bool]] = {}
    for path in sorted(definition.snapshot.root.rglob("*"), key=lambda item: os.fsencode(item.as_posix())):
        relative = pathlib.PurePath(path.relative_to(definition.snapshot.root))
        if relative.as_posix() in {"copier.yml", "copier.yaml"}:
            continue
        if "_copier_conf.answers_file" in relative.as_posix():
            raise ValueError("Templates may not render a Copier answers file.")
        rendered = environment.from_string(relative.as_posix()).render(**answers)
        if path.is_file() and rendered.endswith(".jinja"):
            rendered = rendered.removesuffix(".jinja")
        destination = pathlib.PurePath(rendered)
        windows = pathlib.PureWindowsPath(rendered)
        if (
            not destination.parts
            or destination == pathlib.PurePath(".")
            or destination.is_absolute()
            or windows.is_absolute()
            or windows.drive
            or ".." in destination.parts
            or ".." in windows.parts
            or "\0" in rendered
        ):
            raise ValueError(f"Unsafe rendered path: {rendered}")
        if destination.name in {".copier-answers.yml", ".copier-answers.yaml"}:
            raise ValueError("Templates may not render a Copier answers file.")
        folded = tuple(unicodedata.normalize("NFC", part).casefold() for part in destination.parts)
        if folded in destinations:
            raise ValueError(f"Template paths produce a colliding destination: {destination}")
        for previous, (_, previous_directory) in destinations.items():
            if folded[: len(previous)] == previous and not previous_directory:
                raise ValueError(f"Template paths produce a colliding destination: {destination}")
            if previous[: len(folded)] == folded and not path.is_dir():
                raise ValueError(f"Template paths produce a colliding destination: {destination}")
        destinations[folded] = (destination, path.is_dir())


def _plan(root: pathlib.Path) -> ChangePlan:
    directories: list[CreateDirectory] = []
    files: list[CreateFile] = []
    for path in root.rglob("*"):
        relative = pathlib.PurePath(path.relative_to(root))
        info = path.lstat()
        if stat.S_ISLNK(info.st_mode) or not (stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode)):
            raise ValueError(f"Rendered template contains an unsupported entry: {relative}")
        if stat.S_ISDIR(info.st_mode):
            directories.append(CreateDirectory(relative, mode=0o755))
        else:
            mode = 0o755 if info.st_mode & 0o111 else 0o644
            files.append(CreateFile(relative, path.read_bytes(), mode=mode))
    directories.sort(key=lambda operation: (len(pathlib.PurePath(operation.path).parts), str(operation.path)))
    files.sort(key=lambda operation: str(operation.path))
    return ChangePlan((*directories, *files))


def render_template(definition: TemplateDefinition, answers: typing.Mapping[str, object]) -> ChangePlan:
    resolved = resolve_answers(
        definition.questions,
        answers,
        mode=InteractionMode.NON_INTERACTIVE,
    )
    _rendered_paths(definition, resolved)
    with tempfile.TemporaryDirectory(prefix="kupala-render-") as temporary:
        destination = pathlib.Path(temporary) / "rendered"
        copier.run_copy(
            str(definition.snapshot.root),
            destination,
            data=resolved,
            settings=copier.Settings(),
            defaults=True,
            user_defaults={},
            overwrite=False,
            quiet=True,
            unsafe=False,
            skip_tasks=True,
        )
        return _plan(destination)
