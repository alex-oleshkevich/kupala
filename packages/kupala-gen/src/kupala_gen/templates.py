import dataclasses
import pathlib
import shutil
import tempfile
import tomllib
import typing

import copier
import jinja2
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


def _read_configuration(root: pathlib.Path) -> dict[str, object]:
    path = root / "kupala.toml"
    if not path.exists():
        return {}

    try:
        return tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, tomllib.TOMLDecodeError) as error:
        raise ValueError("Could not read template configuration.") from error


def _question(
    key: str,
    raw: object,
    secrets: list[str],
    earlier: set[str],
) -> Question[typing.Any]:
    if isinstance(raw, dict):
        values = typing.cast(dict[str, object], raw)
    else:
        values = {"default": raw, "type": type(raw).__name__}

    unknown = values.keys() - _QUESTION_FIELDS
    if unknown:
        raise ValueError(f"Unsupported metadata for {key}: {min(unknown)}")

    type_name = values.get("type", "str")
    if not isinstance(type_name, str) or type_name not in _TYPES:
        raise ValueError(f"Unsupported question type for {key}: {type_name}")

    choices = values.get("choices", [])
    default = values.get("default", UNSET)
    required = values.get("required", default is UNSET)
    secret = values.get("secret", key in secrets)
    prompt = values.get("question", values.get("help", key))
    if not isinstance(choices, list):
        raise TypeError(f"Choices for {key} must be a list.")

    if not isinstance(required, bool):
        raise TypeError(f"Requiredness for {key} must be a boolean.")

    if not isinstance(secret, bool):
        raise TypeError(f"Secrecy for {key} must be a boolean.")

    if not isinstance(prompt, str):
        raise TypeError(f"Prompt for {key} must be a string.")

    when_value = values.get("when")
    when = _condition(when_value, earlier, key) if when_value is not None else None
    return Question(
        key,
        prompt,
        type=_TYPES[type_name],
        default=default,
        required=required,
        choices=tuple(choices),
        secret=secret,
        when=when,
    )


def inspect_template(snapshot: TemplateSnapshot) -> TemplateDefinition:
    configuration = _read_configuration(snapshot.root)
    for key in configuration:
        if key.startswith("_") and key != "_secret_questions":
            raise ValueError(f"Unsupported template setting: {key}")

    secrets = configuration.pop("_secret_questions", [])
    if not isinstance(secrets, list) or not all(isinstance(key, str) for key in secrets):
        raise ValueError("_secret_questions must be a list of question names.")

    questions: list[Question[typing.Any]] = []
    earlier: set[str] = set()
    for key, raw in configuration.items():
        if not key:
            raise ValueError("Question names must be non-empty strings.")

        questions.append(_question(key, raw, secrets, earlier))
        earlier.add(key)

    unknown_secrets = set(secrets) - earlier
    if unknown_secrets:
        raise ValueError(f"Unknown secret question: {min(unknown_secrets)}")

    return TemplateDefinition(snapshot, tuple(questions))


def _plan_directory(root: pathlib.Path) -> ChangePlan:
    directories: list[CreateDirectory] = []
    files: list[CreateFile] = []
    for path in root.rglob("*"):
        relative = pathlib.PurePath(path.relative_to(root))
        if relative.name == ".kupala-answers.toml":
            raise ValueError("Templates may not render a Kupala answers file.")

        if path.is_dir():
            directories.append(CreateDirectory(relative, mode=0o755))
        else:
            mode = 0o755 if path.stat().st_mode & 0o111 else 0o644
            files.append(CreateFile(relative, path.read_bytes(), mode=mode))

    directories.sort(key=lambda operation: (len(pathlib.PurePath(operation.path).parts), str(operation.path)))
    files.sort(key=lambda operation: str(operation.path))
    return ChangePlan((*directories, *files))


def render_template(definition: TemplateDefinition, answers: typing.Mapping[str, object]) -> ChangePlan:
    resolved = resolve_answers(definition.questions, answers, mode=InteractionMode.NON_INTERACTIVE)
    with tempfile.TemporaryDirectory(prefix="kupala-render-") as temporary:
        source = pathlib.Path(temporary) / "template"
        shutil.copytree(definition.snapshot.root, source)
        for name in ("kupala.toml", "copier.yml", "copier.yaml"):
            path = source / name
            if path.is_file():
                path.unlink()

        destination = pathlib.Path(temporary) / "rendered"
        copier.run_copy(
            str(source),
            destination,
            data=resolved,
            settings=copier.Settings(),
            defaults=True,
            quiet=True,
            skip_tasks=True,
        )
        return _plan_directory(destination)
