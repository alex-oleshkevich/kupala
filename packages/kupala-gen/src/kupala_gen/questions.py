import dataclasses
import enum
import typing

import click
import questionary


class _Unset:
    __slots__ = ()


UNSET = _Unset()


class InteractionMode(enum.Enum):
    INTERACTIVE = "interactive"
    NON_INTERACTIVE = "non-interactive"
    ASSUME_YES = "assume-yes"


@dataclasses.dataclass(frozen=True, slots=True)
class Question[T]:
    key: str
    prompt: str
    type: click.ParamType[object] | type[object] = str
    default: T | _Unset = UNSET
    required: bool = True
    choices: tuple[T, ...] = ()
    validate: typing.Callable[[T], bool | str | None] | None = None
    when: typing.Callable[[typing.Mapping[str, object]], bool] | None = None
    secret: bool = False
    cli_hint: str | None = None

    def __post_init__(self) -> None:
        if self.secret and self.choices:
            raise ValueError("Secret questions cannot expose choices")


type Ask = typing.Callable[[Question[object]], object]


def _ask(question: Question[object]) -> object:
    if question.choices:
        choices = [questionary.Choice(str(value), value=value) for value in question.choices]
        prompt = (
            questionary.select(question.prompt, choices=choices)
            if question.default is UNSET
            else questionary.select(
                question.prompt,
                choices=choices,
                default=typing.cast(typing.Any, question.default),
            )
        )
    elif question.secret:
        prompt = (
            questionary.password(question.prompt)
            if question.default is UNSET
            else questionary.password(question.prompt, default=str(question.default))
        )
    elif isinstance(click.types.convert_type(question.type), click.types.BoolParamType):
        prompt = (
            questionary.confirm(question.prompt)
            if question.default is UNSET
            else questionary.confirm(question.prompt, default=bool(question.default))
        )
    else:
        prompt = (
            questionary.text(question.prompt)
            if question.default is UNSET
            else questionary.text(question.prompt, default=str(question.default))
        )

    return prompt.unsafe_ask()


def _validate(question: Question[typing.Any], value: object) -> object:
    parameter_type = click.types.convert_type(question.type)
    if value is not None and (isinstance(value, str) or not isinstance(parameter_type, click.types.StringParamType)):
        try:
            value = parameter_type.convert(value, None, None)
        except (click.BadParameter, TypeError, ValueError) as error:
            if question.secret:
                raise click.UsageError(f"Invalid answer for {question.key}") from None
            detail = error.message if isinstance(error, click.BadParameter) else "invalid value"
            raise click.UsageError(f"Invalid answer for {question.key}: {detail}") from error

    if question.choices and value not in question.choices:
        choices = ", ".join(map(str, question.choices))
        raise click.UsageError(f"Invalid answer for {question.key}: choose from {choices}")

    if question.validate is not None:
        try:
            result = question.validate(value)
        except Exception:
            raise click.UsageError(f"Could not validate answer for {question.key}") from None
        if result is False:
            raise click.UsageError(f"Invalid answer for {question.key}")
        if isinstance(result, str):
            if question.secret:
                raise click.UsageError(f"Invalid answer for {question.key}")
            raise click.UsageError(f"Invalid answer for {question.key}: {result}")
    return value


def resolve_answers(
    questions: typing.Sequence[Question[typing.Any]],
    explicit: typing.Mapping[str, object],
    *,
    mode: InteractionMode,
    ask: Ask | None = None,
) -> dict[str, object]:
    known: set[str] = set()
    for question in questions:
        if question.key in known:
            raise ValueError(f"Duplicate question key: {question.key}")
        known.add(question.key)

    unknown = explicit.keys() - known
    if unknown:
        raise click.UsageError(f"Unknown answer: {min(unknown)}")

    answers: dict[str, object] = {}
    missing: list[str] = []
    earlier: set[str] = set()
    prompt = ask or _ask
    for question in questions:
        try:
            active = question.when is None or question.when(answers)
        except KeyError as error:
            dependency = error.args[0] if error.args else None
            if isinstance(dependency, str) and dependency in earlier and dependency not in answers:
                earlier.add(question.key)
                continue
            raise click.UsageError(f"Invalid condition for {question.key}") from None
        except Exception:
            raise click.UsageError(f"Invalid condition for {question.key}") from None
        earlier.add(question.key)
        if not active:
            if question.key in explicit:
                raise click.UsageError(f"Answer supplied for inactive question: {question.key}")
            continue

        if question.key in explicit:
            answers[question.key] = _validate(question, explicit[question.key])
            continue

        if mode is InteractionMode.INTERACTIVE:
            while True:
                try:
                    answers[question.key] = _validate(question, prompt(question))
                    break
                except click.UsageError as error:
                    click.echo(error.message, err=True)
            continue

        if question.default is not UNSET:
            answers[question.key] = _validate(question, question.default)
        elif question.required:
            missing.append(f"{question.key} ({question.cli_hint})" if question.cli_hint else question.key)

    if missing:
        raise click.UsageError(f"Missing required answers: {', '.join(missing)}")
    return answers
