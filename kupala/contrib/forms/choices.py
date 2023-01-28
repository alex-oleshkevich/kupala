import inspect
import typing
import wtforms
from starlette.requests import Request

from kupala.contrib.forms import AsyncForm, Initable, Validator

FormChoices = typing.Sequence[tuple[typing.Any, str]]
ChoicesFactory = typing.Callable[[], FormChoices]
AsyncChoicesFactory = typing.Callable[[Request], typing.Awaitable[FormChoices]]
ChoicesType: typing.TypeAlias = typing.Union[FormChoices, ChoicesFactory, AsyncChoicesFactory]


class AsyncSelectField(wtforms.SelectField, Initable):
    def __init__(
        self,
        label: str | None = None,
        validators: list[Validator] | None = None,
        coerce: typing.Callable = str,
        choices: ChoicesType | None = None,
        validate_choice: bool = True,
        **kwargs: typing.Any,
    ):
        self._choices_factory: AsyncChoicesFactory | None = None
        if inspect.iscoroutinefunction(choices):
            self._choices_factory = choices
            choices = []

        super().__init__(label, validators, coerce, choices, validate_choice, **kwargs)

    async def init(self, form: AsyncForm) -> None:
        if self._choices_factory:
            self.choices = await self._choices_factory(form.context["request"])


class AsyncSelectMultipleField(wtforms.SelectMultipleField, Initable):
    def __init__(
        self,
        label: str | None = None,
        validators: list[Validator] | None = None,
        coerce: typing.Callable = str,
        choices: ChoicesType | None = None,
        validate_choice: bool = True,
        **kwargs: typing.Any,
    ):
        self._choices_factory: AsyncChoicesFactory | None = None
        if inspect.iscoroutinefunction(choices):
            self._choices_factory = choices
            choices = []

        super().__init__(label, validators, coerce, choices, validate_choice, **kwargs)

    async def init(self, form: AsyncForm) -> None:
        if self._choices_factory:
            self.choices = await self._choices_factory(form.context["request"])
