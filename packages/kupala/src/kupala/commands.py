import contextlib
import dataclasses
import functools
import typing

import anyio
import click

from kupala.dependencies import CallPlan, compile_call_plan, resolve_arguments, run_callable

if typing.TYPE_CHECKING:
    from kupala.applications import Kupala
    from kupala.cli import CliContext

type CommandFunction = typing.Callable[..., typing.Any]
type CommandDecorator = typing.Callable[[CommandFunction], CommandFunction]


class UsageError(click.UsageError):
    """A usage error that says what went wrong and what to do about it."""

    def __init__(self, message: str, hint: str, ctx: click.Context | None = None) -> None:
        super().__init__(message, ctx)
        self.add_note(f"hint: {hint}")

    def format_message(self) -> str:
        return "\n".join((self.message, *self.__notes__))


def current_application() -> Kupala:
    """The application the current command runs against."""

    # a command mounted on a group Kupala did not build reaches this with no context object at all,
    # which is the same "no application" story rather than an AttributeError from the attribute below
    context: CliContext | None = click.get_current_context().find_root().obj
    if context is None or context.app is None:
        raise UsageError(
            "This command needs an application and none was loaded.",
            "Set KUPALA_APP to 'module:attribute', or run the command through Kupala.cli().",
        )

    return context.app


@dataclasses.dataclass(frozen=True, slots=True)
class CommandDefinition:
    name: str | None
    fn: CommandFunction
    with_lifespan: bool
    attrs: dict[str, typing.Any]


class Commands:
    """A declarative registry of commands, mirroring how `Routes` collects endpoints."""

    option = staticmethod(click.option)
    argument = staticmethod(click.argument)
    group = staticmethod(click.group)
    confirmation_option = staticmethod(click.confirmation_option)
    password_option = staticmethod(click.password_option)

    def __init__(self) -> None:
        self.definitions: list[CommandDefinition] = []

    def command(self, name: str | None = None, *, with_lifespan: bool = True, **attrs: typing.Any) -> CommandDecorator:
        """Register a command."""

        def decorator(fn: CommandFunction) -> CommandFunction:
            self.definitions.append(
                CommandDefinition(
                    name=name,
                    fn=fn,
                    with_lifespan=with_lifespan,
                    attrs=attrs,
                )
            )
            return fn

        return decorator

    def add(self, definition: CommandDefinition) -> None:
        self.definitions.append(definition)

    def compile(self) -> list[click.Command]:
        return [build_command(definition) for definition in self.definitions]


def build_command(definition: CommandDefinition) -> click.Command:
    """Turn a definition into a click command whose callback runs through the injector."""

    plan = compile_call_plan(definition.fn)

    @functools.wraps(definition.fn)
    def placeholder(**kwargs: typing.Any) -> None:
        # click derives the command name and help text from this function, then the real callback
        # below replaces it, so this body is never reached
        raise AssertionError("the placeholder callback is replaced before the command is registered")

    # click consumes __click_params__ destructively, so hand it a copy and leave the original intact
    typing.cast(typing.Any, placeholder).__click_params__ = list(
        getattr(definition.fn, "__click_params__", []),
    )
    # the extra attributes are an untyped mapping, which loses click's overload, so the decorator's
    # shape is restated here rather than leaking Any into the return type
    decorate = typing.cast(
        typing.Callable[[CommandFunction], click.Command],
        click.command(name=definition.name, **definition.attrs),
    )
    command = decorate(placeholder)

    # expose_value=False parameters appear here but are never passed to the callback, so they stay
    # injectable rather than being dropped from the plan and then never filled
    owned = frozenset(parameter.name for parameter in command.params if parameter.expose_value and parameter.name)
    injected = dataclasses.replace(
        plan,
        parameters=tuple(parameter for parameter in plan.parameters if parameter.param.name not in owned),
    )

    def callback(**kwargs: typing.Any) -> None:
        execute(current_application(), injected, kwargs, with_lifespan=definition.with_lifespan)

    command.callback = callback
    return command


def execute(
    app: Kupala,
    injected: CallPlan[..., typing.Any],
    click_arguments: dict[str, typing.Any],
    *,
    with_lifespan: bool,
) -> None:
    """Run a command callback inside the application lifespan and an invocation context."""

    async def main() -> None:
        async with contextlib.AsyncExitStack() as stack:
            state: dict[str, typing.Any] = {}
            if with_lifespan:
                state = await stack.enter_async_context(app.lifespan())

            context = app.invocation_context(state)
            await stack.enter_async_context(context)
            arguments = await resolve_arguments(injected, context)
            await run_callable(injected.callable, {**arguments, **click_arguments})

    anyio.run(main)
