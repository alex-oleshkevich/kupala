import dataclasses
import importlib
import importlib.metadata
import logging
import os
import typing

import click

from kupala.applications import Kupala
from kupala.commands import BootstrapCommand, Commands, UsageError

APP_ENV_VAR = "KUPALA_APP"
APP_GROUP = "kupala.app"
PLUGIN_GROUP = "kupala.commands"

logger = logging.getLogger(__name__)


def import_app(value: str, source: str) -> Kupala:
    """Import the application at `module:attribute`, naming `source` in anything that goes wrong."""

    module_name, separator, attribute = value.partition(":")
    if not separator or not module_name or not attribute:
        raise UsageError(
            f"{value!r} (from {source}) is not a valid application path.",
            "Use the 'module:attribute' form, for example 'demo.app:app'.",
        )

    try:
        module = importlib.import_module(module_name)
    except ModuleNotFoundError as exc:
        # a dependency missing *inside* the application is the application's bug, and its traceback is
        # the useful output; only a pointer at a module that does not exist is a usage error
        if exc.name != module_name and not module_name.startswith(f"{exc.name}."):
            raise

        raise UsageError(
            f"Cannot import {module_name!r} (from {source}): {exc}.",
            "Check the module path, and that the project is installed in this environment.",
        ) from exc

    app = getattr(module, attribute, None)
    if app is None:
        raise UsageError(
            f"Module {module_name!r} has no attribute {attribute!r} (from {source}).",
            f"Check that {attribute!r} is defined in {module_name!r}.",
        )

    if not isinstance(app, Kupala):
        raise UsageError(
            f"{value!r} (from {source}) is a {type(app).__name__}, not a Kupala application.",
            "Point the application path at a Kupala instance.",
        )

    return app


def app_from_entry_points() -> str | None:
    """The application path a project installed in this environment declares, if exactly one does.

    Discovery reads installed distribution metadata rather than the working directory, so standing in
    a checkout never makes that checkout's code run; declaring an application is an install-time act.
    """

    entry_points = list(importlib.metadata.entry_points(group=APP_GROUP))
    if not entry_points:
        return None

    if len(entry_points) > 1:
        declared = ", ".join(sorted(entry_point.value for entry_point in entry_points))
        raise UsageError(
            f"Several installed projects declare a {APP_GROUP!r} application: {declared}.",
            f"Set {APP_ENV_VAR} to the one this invocation runs against.",
        )

    return entry_points[0].value


def resolve_application(app: Kupala | None = None) -> Kupala | None:
    """The application this invocation runs against, or None when nothing names one.

    An application handed in beats the environment, which beats what the environment has installed:
    each step is a broader statement of intent than the one after it.
    """

    if app is not None:
        return app

    # the variable is read on its own rather than as a default, which would walk the entry points
    # even when it is set
    if pointer := os.environ.get(APP_ENV_VAR):
        return import_app(pointer, APP_ENV_VAR)

    if pointer := app_from_entry_points():
        return import_app(pointer, f"the {APP_GROUP!r} entry point")

    return None


def load_plugins(cli: click.Group, group: str = PLUGIN_GROUP) -> None:
    """Let installed packages register their commands on the command line."""

    for entry_point in importlib.metadata.entry_points(group=group):
        try:
            plugin = entry_point.load()
        except Exception:  # noqa: BLE001 - a third-party module may raise anything on import
            logger.warning("Ignoring CLI plugin %r: import failed.", entry_point.name)
            continue

        # a click.Command is callable, and calling one would try to *run* it rather than register it
        if isinstance(plugin, click.Command) or not callable(plugin):
            logger.warning(
                "Ignoring CLI plugin %r: expected a registration callback, got %s.",
                entry_point.name,
                type(plugin).__name__,
            )
            continue

        registration = Commands()
        try:
            plugin(registration)
            commands = registration.compile()
        except Exception:  # noqa: BLE001 - a third-party plugin may raise anything
            logger.warning("Ignoring CLI plugin %r: registration failed.", entry_point.name)
            continue

        for command in commands:
            cli.add_command(command)


@dataclasses.dataclass
class CliContext:
    """What every command can reach through the click context object.

    Commands read this off the root context rather than taking it as an argument, so anything the
    command line learns about an invocation can be added here without touching a single signature.
    """

    application: Kupala | None


class _LazyGroup(click.Group):
    def __init__(
        self,
        *args: typing.Any,
        context: CliContext,
        **kwargs: typing.Any,
    ) -> None:
        self._context = context
        self._application_loaded = False
        self._application_error: Exception | None = None
        super().__init__(*args, **kwargs)

    def get_command(self, ctx: click.Context, cmd_name: str) -> click.Command | None:
        command = super().get_command(ctx, cmd_name)
        if isinstance(command, (click.Group, BootstrapCommand)):
            return command

        self._load_application_commands()
        return super().get_command(ctx, cmd_name)

    def list_commands(self, ctx: click.Context) -> list[str]:
        if not ctx.resilient_parsing:
            try:
                self._load_application_commands()
            except Exception:  # noqa: BLE001, S110 - root help still lists installed commands
                pass
        return super().list_commands(ctx)

    def _load_application_commands(self) -> None:
        if self._application_error is not None:
            raise self._application_error
        if self._application_loaded:
            return

        try:
            self._context.application = resolve_application(self._context.application)
            if self._context.application is not None:
                for command in self._context.application.commands:
                    name = typing.cast(str, command.name)
                    if not isinstance(self.commands.get(name), (click.Group, BootstrapCommand)):
                        self.add_command(command)

        except Exception as error:
            self._application_error = error
            raise
        self._application_loaded = True


def build_cli(app: Kupala | None) -> click.Group:
    """Build the command line for one invocation."""

    context = CliContext(application=app)

    @click.group(
        cls=_LazyGroup,
        context=context,
        context_settings={"help_option_names": ["-h", "--help"]},
    )
    @click.version_option(package_name="kupala")
    @click.pass_context
    def cli(ctx: click.Context) -> None:
        """Kupala command line interface."""
        ctx.obj = context

    load_plugins(cli, PLUGIN_GROUP)
    return cli


def main(args: typing.Sequence[str] | None = None, *, app: Kupala | None = None) -> int:
    """Run the CLI and return its exit code."""

    try:
        cli = build_cli(app)
        result = cli.main(args=args, standalone_mode=False)
    except click.ClickException as exc:
        exc.show()
        return exc.exit_code
    except click.exceptions.Abort as exc:
        click.echo("Aborted.", err=True)
        # click turns Ctrl-C into Abort, and a signal exit is 128 + SIGINT
        return 130 if isinstance(exc.__cause__, KeyboardInterrupt) else 1

    return result if isinstance(result, int) else 0
