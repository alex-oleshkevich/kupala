import dataclasses
import importlib
import importlib.metadata
import logging
import os
import pathlib
import tomllib
import typing

import click

from kupala.applications import Kupala
from kupala.commands import UsageError

APP_ENV_VAR = "KUPALA_APP"
PLUGIN_GROUP = "kupala.commands"

logger = logging.getLogger(__name__)


def import_app(value: str) -> Kupala:
    """Import the application at `module:attribute`."""

    module_name, separator, attribute = value.partition(":")
    if not separator or not module_name or not attribute:
        raise UsageError(
            f"{value!r} (from {value}) is not a valid application path.",
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
            f"Cannot import {module_name!r} (from {value}): {exc}.",
            "Check the module path, and that the project is installed in this environment.",
        ) from exc

    app = getattr(module, attribute, None)
    if app is None:
        raise UsageError(
            f"Module {module_name!r} has no attribute {attribute!r} (from {value}).",
            f"Check that {attribute!r} is defined in {module_name!r}.",
        )

    if not isinstance(app, Kupala):
        raise UsageError(
            f"{value!r} (from {value}) is a {type(app).__name__}, not a Kupala application.",
            "Point the application path at a Kupala instance.",
        )

    return app


def _guess_app_from_pyproject() -> str | None:
    # `parents` starts at the directory itself and is finite; walking with os.path.dirname would both
    # skip the working directory and spin forever, because dirname("/") is "/"
    cwd = pathlib.Path.cwd()
    for location in (cwd, *cwd.parents):
        pyproject_path = location / "pyproject.toml"
        if pyproject_path.is_file():
            with pyproject_path.open("rb") as f:
                data = tomllib.load(f)
                tool_config: dict[str, str] = data.get("tool", {}).get("kupala", {})
                return tool_config.get("app", None)

    return None


def resolve_application() -> Kupala | None:
    """The application this invocation runs against, or None when nothing names one."""

    if app_path := os.environ.get(APP_ENV_VAR, _guess_app_from_pyproject()):
        return import_app(app_path)
    return None


type Plugin = typing.Callable[[click.Group], None]


def load_plugins(cli: click.Group) -> None:
    """Let installed packages register their commands on the command line.."""

    for entry_point in importlib.metadata.entry_points(group=PLUGIN_GROUP):
        try:
            plugin = entry_point.load()
        except Exception as exc:  # noqa: BLE001 - a third-party module may raise anything on import
            logger.warning("Ignoring CLI plugin %r, which failed to load: %s", entry_point.name, exc)
            continue

        # a click.Command is callable, and calling one would try to *run* it rather than register it
        if isinstance(plugin, click.Command) or not callable(plugin):
            logger.warning(
                "Ignoring CLI plugin %r: expected a callable taking the root group, got %s.",
                entry_point.name,
                type(plugin).__name__,
            )
            continue

        try:
            plugin(cli)
        except Exception as exc:  # noqa: BLE001 - a third-party plugin may raise anything
            logger.warning("Ignoring CLI plugin %r, which failed while registering: %s", entry_point.name, exc)


class _Group(click.Group): ...


def build_cli() -> click.Group:
    """Build the command line for one invocation, with every command already registered."""

    app = resolve_application()

    @click.group(cls=_Group, context_settings={"help_option_names": ["-h", "--help"]})
    @click.version_option(package_name="kupala")
    @click.pass_context
    def cli(ctx: click.Context) -> None:
        """Kupala command line interface."""
        ctx.obj = CliContext(app=app)

    load_plugins(cli)
    if app is not None:
        for command in app.commands or []:
            cli.add_command(command)
    print(app)

    return cli


def main(args: typing.Sequence[str] | None = None, *, app: Kupala | None = None) -> int:
    """Run the CLI and return its exit code."""

    try:
        cli = build_cli()
        result = cli.main(args=args, standalone_mode=False)
    except click.ClickException as exc:
        exc.show()
        return exc.exit_code
    except click.exceptions.Abort as exc:
        click.echo("Aborted.", err=True)
        # click turns Ctrl-C into Abort, and a signal exit is 128 + SIGINT
        return 130 if isinstance(exc.__cause__, KeyboardInterrupt) else 1

    return result if isinstance(result, int) else 0


@dataclasses.dataclass
class CliContext:
    app: Kupala | None
