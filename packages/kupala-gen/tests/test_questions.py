import traceback
import typing

import click
import pytest
import questionary

from kupala_gen.questions import UNSET, InteractionMode, Question, resolve_answers


class Answers:
    def __init__(self, *values: object) -> None:
        self.values = iter(values)
        self.calls: list[Question[object]] = []

    def __call__(self, question: Question[object]) -> object:
        self.calls.append(question)
        return next(self.values)


class TestResolveAnswers:
    def test_preserves_every_explicit_value(self) -> None:
        questions: tuple[Question[object], ...] = tuple(
            Question(key, key, required=False) for key in ("false", "zero", "empty", "none")
        )

        answers = resolve_answers(
            questions,
            {"false": False, "zero": 0, "empty": "", "none": None},
            mode=InteractionMode.NON_INTERACTIVE,
        )

        assert answers == {"false": False, "zero": 0, "empty": "", "none": None}

    def test_interviews_before_using_a_default(self) -> None:
        ask = Answers("asked")

        answers = resolve_answers(
            (Question("name", "Name", default="default"),),
            {},
            mode=InteractionMode.INTERACTIVE,
            ask=ask,
        )

        assert answers == {"name": "asked"}
        assert len(ask.calls) == 1

    def test_uses_defaults_without_interaction(self) -> None:
        answers = resolve_answers(
            (Question("count", "Count", type=int, default=2),),
            {},
            mode=InteractionMode.NON_INTERACTIVE,
        )

        assert answers == {"count": 2}

    def test_lists_all_missing_required_answers(self) -> None:
        questions: tuple[Question[object], ...] = (
            Question("name", "Name", cli_hint="--name"),
            Question("kind", "Kind"),
        )

        with pytest.raises(click.UsageError) as caught:
            resolve_answers(questions, {}, mode=InteractionMode.ASSUME_YES)

        assert "name (--name)" in caught.value.message
        assert "kind" in caught.value.message

    def test_rejects_unknown_answers(self) -> None:
        with pytest.raises(click.UsageError, match="Unknown answer: other"):
            resolve_answers((), {"other": "value"}, mode=InteractionMode.NON_INTERACTIVE)

    def test_conditions_only_see_earlier_answers(self) -> None:
        questions: tuple[Question[object], ...] = (
            Question("kind", "Kind"),
            Question("name", "Name", when=lambda answers: answers["kind"] == "named"),
        )

        answers = resolve_answers(
            questions,
            {"kind": "plain"},
            mode=InteractionMode.NON_INTERACTIVE,
        )

        assert answers == {"kind": "plain"}

    def test_rejects_an_explicit_inactive_answer(self) -> None:
        questions: tuple[Question[object], ...] = (
            Question("kind", "Kind"),
            Question("name", "Name", when=lambda answers: answers["kind"] == "named"),
        )

        with pytest.raises(click.UsageError, match="inactive question: name"):
            resolve_answers(
                questions,
                {"kind": "plain", "name": "unused"},
                mode=InteractionMode.NON_INTERACTIVE,
            )

    def test_skips_a_condition_when_an_earlier_answer_is_missing(self) -> None:
        questions: tuple[Question[object], ...] = (
            Question("kind", "Kind"),
            Question("name", "Name", when=lambda answers: answers["kind"] == "named"),
            Question("module", "Module"),
        )

        with pytest.raises(click.UsageError) as caught:
            resolve_answers(questions, {}, mode=InteractionMode.NON_INTERACTIVE)

        assert "kind" in caught.value.message
        assert "module" in caught.value.message
        assert "name" not in caught.value.message

    def test_rejects_an_explicit_answer_when_its_condition_cannot_be_evaluated(self) -> None:
        questions: tuple[Question[object], ...] = (
            Question("kind", "Kind", required=False),
            Question("name", "Name", when=lambda answers: answers["kind"] == "named"),
        )

        with pytest.raises(click.UsageError, match="Answer supplied for inactive question: name"):
            resolve_answers(
                questions,
                {"name": "widget"},
                mode=InteractionMode.NON_INTERACTIVE,
            )

    def test_unrelated_missing_answers_do_not_disable_a_condition(self) -> None:
        questions: tuple[Question[object], ...] = (
            Question("unrelated", "Unrelated"),
            Question("enabled", "Enabled", type=bool),
            Question("name", "Name", when=lambda answers: bool(answers["enabled"])),
        )

        with pytest.raises(click.UsageError) as caught:
            resolve_answers(
                questions,
                {"enabled": True},
                mode=InteractionMode.NON_INTERACTIVE,
            )

        assert "unrelated" in caught.value.message
        assert "name" in caught.value.message

    @pytest.mark.parametrize("dependency", ["unknown", "later"])
    def test_rejects_conditions_that_read_non_previous_answers(self, dependency: str) -> None:
        questions: tuple[Question[object], ...] = (
            Question("name", "Name", when=lambda answers: bool(answers[dependency])),
            Question("later", "Later", required=False),
        )

        with pytest.raises(click.UsageError, match="Invalid condition for name"):
            resolve_answers(
                questions,
                {"name": "explicit"},
                mode=InteractionMode.NON_INTERACTIVE,
            )

    def test_reports_a_condition_that_cannot_be_evaluated(self) -> None:
        def invalid(answers: typing.Mapping[str, object]) -> bool:
            raise RuntimeError("failed")

        with pytest.raises(click.UsageError, match="Invalid condition for name"):
            resolve_answers(
                (Question("name", "Name", when=invalid),),
                {},
                mode=InteractionMode.NON_INTERACTIVE,
            )

    def test_converts_and_validates_explicit_answers(self) -> None:
        question = Question(
            "count",
            "Count",
            type=int,
            choices=(1, 2),
            validate=lambda value: "must be two" if value != 2 else None,
        )

        assert resolve_answers((question,), {"count": "2"}, mode=InteractionMode.NON_INTERACTIVE) == {"count": 2}
        with pytest.raises(click.UsageError, match="must be two"):
            resolve_answers((question,), {"count": "1"}, mode=InteractionMode.NON_INTERACTIVE)

    def test_rejects_a_value_outside_the_choices(self) -> None:
        with pytest.raises(click.UsageError, match="choose from one, two"):
            resolve_answers(
                (Question("kind", "Kind", choices=("one", "two")),),
                {"kind": "three"},
                mode=InteractionMode.NON_INTERACTIVE,
            )

    def test_rejects_an_invalid_non_string_typed_value(self) -> None:
        with pytest.raises(click.UsageError, match="Invalid answer for count"):
            resolve_answers(
                (Question("count", "Count", type=int),),
                {"count": ["bad"]},
                mode=InteractionMode.NON_INTERACTIVE,
            )

    def test_rejects_a_false_validator_result(self) -> None:
        with pytest.raises(click.UsageError, match="Invalid answer for name"):
            resolve_answers(
                (Question("name", "Name", validate=lambda value: False),),
                {"name": "value"},
                mode=InteractionMode.NON_INTERACTIVE,
            )

    def test_retries_invalid_interactive_answers(self) -> None:
        ask = Answers("bad", "2")
        question = Question[int]("count", "Count", type=int)

        answers = resolve_answers((question,), {}, mode=InteractionMode.INTERACTIVE, ask=ask)

        assert answers == {"count": 2}
        assert len(ask.calls) == 2

    def test_secret_conversion_errors_do_not_include_the_value(self) -> None:
        secret = "-".join(("top", "secret"))  # noqa: FLY002 - keep it out of traceback source
        with pytest.raises(click.UsageError) as caught:
            resolve_answers(
                (Question("token", "Token", type=int, secret=True),),
                {"token": secret},
                mode=InteractionMode.NON_INTERACTIVE,
            )

        assert "top-secret" not in "".join(traceback.format_exception(caught.value))

    def test_secret_validator_exceptions_do_not_include_the_value(self) -> None:
        secret = "-".join(("top", "secret"))  # noqa: FLY002 - keep it out of traceback source

        def validate(value: str) -> bool:
            raise RuntimeError(f"rejected {value}")

        with pytest.raises(click.UsageError) as caught:
            resolve_answers(
                (Question("token", "Token", secret=True, validate=validate),),
                {"token": secret},
                mode=InteractionMode.NON_INTERACTIVE,
            )

        assert "top-secret" not in "".join(traceback.format_exception(caught.value))

    def test_secret_validator_messages_do_not_include_the_value(self) -> None:
        with pytest.raises(click.UsageError) as caught:
            resolve_answers(
                (
                    Question(
                        "token",
                        "Token",
                        secret=True,
                        validate=lambda value: f"rejected {value}",
                    ),
                ),
                {"token": "top-secret"},
                mode=InteractionMode.NON_INTERACTIVE,
            )

        assert "top-secret" not in caught.value.message

    def test_rejects_duplicate_question_keys(self) -> None:
        with pytest.raises(ValueError, match="Duplicate question key: name"):
            resolve_answers(
                (Question("name", "Name"), Question("name", "Again")),
                {},
                mode=InteractionMode.NON_INTERACTIVE,
            )

    def test_optional_unanswered_questions_are_absent(self) -> None:
        answers = resolve_answers(
            (Question("name", "Name", default=UNSET, required=False),),
            {},
            mode=InteractionMode.NON_INTERACTIVE,
        )

        assert answers == {}

    def test_secret_questions_reject_visible_choices(self) -> None:
        with pytest.raises(ValueError, match="Secret questions"):
            Question("token", "Token", choices=("one", "two"), secret=True)


class Prompt:
    def __init__(self, answer: object) -> None:
        self.answer = answer

    def unsafe_ask(self) -> object:
        return self.answer


class TestQuestionary:
    @pytest.mark.parametrize(
        ("question", "method", "answer"),
        [
            (Question("name", "Name"), "text", "widget"),
            (Question("token", "Token", secret=True), "password", "secret"),
            (Question("kind", "Kind", choices=(1, 2)), "select", 2),
        ],
    )
    def test_uses_the_matching_questionary_prompt(
        self,
        monkeypatch: pytest.MonkeyPatch,
        question: Question[object],
        method: str,
        answer: object,
    ) -> None:
        called: list[tuple[object, ...]] = []

        def prompt(*args: object, **kwargs: object) -> Prompt:
            called.append((*args, kwargs))
            return Prompt(answer)

        monkeypatch.setattr(questionary, method, prompt)

        assert resolve_answers((question,), {}, mode=InteractionMode.INTERACTIVE) == {question.key: answer}
        assert called

    def test_none_is_a_valid_interactive_answer(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(questionary, "text", lambda *args, **kwargs: Prompt(None))

        assert resolve_answers((Question("name", "Name"),), {}, mode=InteractionMode.INTERACTIVE) == {"name": None}

    @pytest.mark.parametrize(
        ("question", "method", "expected"),
        [
            (Question("name", "Name", default="widget"), "text", "widget"),
            (Question("count", "Count", type=int, default=2), "text", "2"),
            (Question("enabled", "Enabled", type=bool, default=True), "confirm", True),
            (Question("token", "Token", default="secret", secret=True), "password", "secret"),
        ],
    )
    def test_passes_a_declared_default_to_questionary(
        self,
        monkeypatch: pytest.MonkeyPatch,
        question: Question[object],
        method: str,
        expected: object,
    ) -> None:
        defaults: list[object] = []

        def prompt(prompt: str, *, default: object) -> Prompt:
            defaults.append(default)
            return Prompt(default)

        monkeypatch.setattr(questionary, method, prompt)

        answers = resolve_answers(
            (question,),
            {},
            mode=InteractionMode.INTERACTIVE,
        )

        assert answers == {question.key: question.default}
        assert defaults == [expected]

    @pytest.mark.parametrize("error", [EOFError(), KeyboardInterrupt()])
    def test_propagates_interview_interrupts(self, monkeypatch: pytest.MonkeyPatch, error: BaseException) -> None:
        class InterruptedPrompt:
            def unsafe_ask(self) -> object:
                raise error

        monkeypatch.setattr(questionary, "text", lambda *args, **kwargs: InterruptedPrompt())

        with pytest.raises(type(error)):
            resolve_answers((Question("name", "Name"),), {}, mode=InteractionMode.INTERACTIVE)
