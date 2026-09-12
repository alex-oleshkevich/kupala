"""Discover generators contributed by installed packages."""

import importlib.metadata
import typing

import click
from click.shell_completion import CompletionItem

GENERATOR_GROUP = "kupala.generators"


def _provider(entry_point: importlib.metadata.EntryPoint) -> str:
    distribution = entry_point.dist
    name = distribution.name if distribution is not None else "unknown distribution"
    return f"{name} ({entry_point.value})"


class GeneratorGroup(click.Group):
    """A Click group that imports only the selected generator."""

    def __init__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        super().__init__(*args, **kwargs)
        self._entry_points: dict[str, list[importlib.metadata.EntryPoint]] = {}
        for entry_point in importlib.metadata.entry_points(group=GENERATOR_GROUP):
            self._entry_points.setdefault(entry_point.name, []).append(entry_point)

        for entry_points in self._entry_points.values():
            entry_points.sort(key=_provider)

    def list_commands(self, ctx: click.Context) -> list[str]:
        return sorted(self._entry_points)

    def get_command(self, ctx: click.Context, cmd_name: str) -> click.Command | None:
        entry_points = self._entry_points.get(cmd_name)
        if entry_points is None:
            return None

        if len(entry_points) > 1:
            providers = ", ".join(map(_provider, entry_points))
            raise click.ClickException(f"Generator {cmd_name!r} is declared more than once: {providers}.")

        entry_point = entry_points[0]

        try:
            command = entry_point.load()
        except Exception:  # noqa: BLE001 - third-party imports may raise anything
            raise click.ClickException(
                f"Could not load generator {cmd_name!r} from {_provider(entry_point)}. Reinstall or remove that package.",
            ) from None

        if not isinstance(command, click.Command):
            raise click.ClickException(f"Generator {cmd_name!r} expected a Click command.")

        return command

    def format_commands(self, ctx: click.Context, formatter: click.HelpFormatter) -> None:
        rows: list[tuple[str, str]] = []
        for name in self.list_commands(ctx):
            entry_points = self._entry_points[name]
            providers = ", ".join(map(_provider, entry_points))
            prefix = "unavailable: " if len(entry_points) > 1 else "from "
            rows.append((name, prefix + providers))

        if rows:
            with formatter.section("Commands"):
                formatter.write_dl(rows)

    def shell_complete(self, ctx: click.Context, incomplete: str) -> list[CompletionItem]:
        commands = [CompletionItem(name) for name in self.list_commands(ctx) if name.startswith(incomplete)]
        return [*commands, *click.Command.shell_complete(self, ctx, incomplete)]
