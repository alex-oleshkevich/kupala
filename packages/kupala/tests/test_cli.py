import contextlib
import importlib.metadata
import logging
import pathlib
import sys
import typing

import click
import pytest

from kupala import cli
from kupala import commands as commands_module
from kupala.applications import Kupala
from kupala.dependencies import FromState, Value
from kupala.routing import Routes

type Currency = typing.Annotated[str, Value("EUR")]
type Greeting = typing.Annotated[str, FromState(lambda ctx, state: state.greeting)]


class AppEntryPoint:
    """Stands in for an installed distribution declaring the application it ships."""

    def __init__(self, value: str) -> None:
        self.value = value


class PluginEntryPoint:
    """Stands in for an installed distribution contributing commands."""

    def __init__(self, name: str, loader: typing.Callable[[], typing.Any]) -> None:
        self.name = name
        self._loader = loader

    def load(self) -> typing.Any:
        return self._loader()


def installed(
    monkeypatch: pytest.MonkeyPatch,
    *,
    apps: typing.Sequence[AppEntryPoint] = (),
    plugins: typing.Sequence[PluginEntryPoint] = (),
) -> None:
    """Pin what this environment has installed, so a test never sees the real one.

    Both discovery groups are stubbed together: the demo project declares an application, and the
    suite would otherwise import it whenever a test expects to find none.
    """

    groups: dict[str, typing.Sequence[typing.Any]] = {cli.APP_GROUP: apps, cli.PLUGIN_GROUP: plugins}
    monkeypatch.delenv(cli.APP_ENV_VAR, raising=False)
    monkeypatch.setattr(importlib.metadata, "entry_points", lambda *, group: groups[group])


SAMPLE_MODULE = """
import click

from kupala.applications import Kupala
from kupala.routing import Routes

NOT_AN_APP = object()
app = Kupala(
    __name__,
    routes=Routes(),
    commands=[click.Command(name="sample", callback=lambda: click.echo("sample ran"))],
)
"""


def write_app_module(root: pathlib.Path) -> str:
    """Write an importable module holding a sample application, named uniquely for this test."""

    name = f"sample_{root.name}"
    (root / f"{name}.py").write_text(SAMPLE_MODULE)
    return name


def make_app(
    commands: commands_module.Commands | typing.Sequence[click.Command] = (),
    greeting: str = "hi",
) -> Kupala:
    @contextlib.asynccontextmanager
    async def lifespan(app: Kupala) -> typing.AsyncGenerator[dict[str, typing.Any]]:
        yield {"greeting": greeting}

    return Kupala(__name__, routes=Routes(), commands=commands, lifespans=[lifespan])


class TestImportApp:
    def test_imports_the_application(self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.syspath_prepend(str(tmp_path))
        module = write_app_module(tmp_path)

        assert isinstance(cli.import_app(f"{module}:app", cli.APP_ENV_VAR), Kupala)

    @pytest.mark.parametrize("value", ["notvalid", ":app", "module:"])
    def test_rejects_a_malformed_path(self, value: str) -> None:
        with pytest.raises(click.UsageError, match="is not a valid application path"):
            cli.import_app(value, cli.APP_ENV_VAR)

    def test_reports_a_module_that_cannot_be_imported(self) -> None:
        with pytest.raises(click.UsageError, match="Cannot import"):
            cli.import_app("kupala_does_not_exist:app", cli.APP_ENV_VAR)

    def test_reports_a_missing_parent_package(self) -> None:
        """The import names the parent, so a missing one still points at the path the user gave."""

        with pytest.raises(click.UsageError, match="Cannot import 'kupala_does_not_exist.sub'"):
            cli.import_app("kupala_does_not_exist.sub:app", cli.APP_ENV_VAR)

    def test_reports_a_missing_attribute(self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.syspath_prepend(str(tmp_path))
        module = write_app_module(tmp_path)

        with pytest.raises(click.UsageError, match="has no attribute"):
            cli.import_app(f"{module}:missing", cli.APP_ENV_VAR)

    def test_reports_an_attribute_that_is_not_an_application(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.syspath_prepend(str(tmp_path))
        module = write_app_module(tmp_path)

        with pytest.raises(click.UsageError, match="is a object, not a Kupala application"):
            cli.import_app(f"{module}:NOT_AN_APP", cli.APP_ENV_VAR)

    def test_names_the_source_of_the_path(self) -> None:
        """A pointer can come from the variable or from installed metadata; the error says which."""

        with pytest.raises(click.UsageError) as caught:
            cli.import_app("notvalid", "the 'kupala.app' entry point")

        assert "(from the 'kupala.app' entry point)" in caught.value.format_message()

    def test_lets_the_application_own_import_error_through(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A dependency missing inside the application is the application's bug, not a usage error."""

        monkeypatch.syspath_prepend(str(tmp_path))
        (tmp_path / "broken_import.py").write_text("import kupala_no_such_dependency\n")

        with pytest.raises(ModuleNotFoundError, match="kupala_no_such_dependency"):
            cli.import_app("broken_import:app", cli.APP_ENV_VAR)


class TestAppFromEntryPoints:
    def test_finds_nothing_when_no_project_declares_one(self, monkeypatch: pytest.MonkeyPatch) -> None:
        installed(monkeypatch)

        assert cli.app_from_entry_points() is None

    def test_returns_the_declared_path(self, monkeypatch: pytest.MonkeyPatch) -> None:
        installed(monkeypatch, apps=[AppEntryPoint("demo.app:app")])

        assert cli.app_from_entry_points() == "demo.app:app"

    def test_refuses_to_choose_between_several(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Entry points are environment-wide, so picking one silently would run the wrong project."""

        installed(monkeypatch, apps=[AppEntryPoint("second.app:app"), AppEntryPoint("first.app:app")])

        with pytest.raises(click.UsageError) as caught:
            cli.app_from_entry_points()

        message = caught.value.format_message()
        assert "first.app:app, second.app:app" in message
        assert cli.APP_ENV_VAR in message


class TestResolveApplication:
    def test_an_application_handed_in_wins(self, monkeypatch: pytest.MonkeyPatch) -> None:
        installed(monkeypatch, apps=[AppEntryPoint("never.imported:app")])
        monkeypatch.setenv(cli.APP_ENV_VAR, "never.imported:app")
        app = make_app()

        assert cli.resolve_application(app) is app

    def test_the_variable_beats_installed_metadata(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The variable is an act of this invocation, so it overrides what the environment declares."""

        installed(monkeypatch, apps=[AppEntryPoint("never.imported:app")])
        monkeypatch.syspath_prepend(str(tmp_path))
        module = write_app_module(tmp_path)
        monkeypatch.setenv(cli.APP_ENV_VAR, f"{module}:app")

        assert cli.resolve_application() is not None

    def test_imports_what_an_installed_project_declares(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.syspath_prepend(str(tmp_path))
        module = write_app_module(tmp_path)
        installed(monkeypatch, apps=[AppEntryPoint(f"{module}:app")])

        assert cli.resolve_application() is not None

    def test_finds_nothing_when_nothing_names_one(self, monkeypatch: pytest.MonkeyPatch) -> None:
        installed(monkeypatch)

        assert cli.resolve_application() is None

    def test_a_variable_that_does_not_import_is_an_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Setting it is a statement of intent, so failing to import one is loud, never a silent miss."""

        installed(monkeypatch)
        monkeypatch.setenv(cli.APP_ENV_VAR, "never.imported:app")

        with pytest.raises(click.UsageError, match="Cannot import"):
            cli.resolve_application()

    def test_an_empty_variable_is_ignored(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """An exported-but-empty variable is how shells spell "unset", and must not be a usage error."""

        installed(monkeypatch)
        monkeypatch.setenv(cli.APP_ENV_VAR, "")

        assert cli.resolve_application() is None

    def test_never_reads_the_working_directory(self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Running the CLI inside an untrusted checkout must not import anything that checkout holds."""

        installed(monkeypatch)
        monkeypatch.chdir(tmp_path)
        write_app_module(tmp_path)
        (tmp_path / "pyproject.toml").write_text('[tool.kupala]\napp = "sample:app"\n')
        before = list(sys.path)

        assert cli.resolve_application() is None
        assert sys.path == before


class TestLoadPlugins:
    def test_lets_a_plugin_register_its_commands(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def register(group: click.Group) -> None:
            group.add_command(click.Command(name="plugged", callback=lambda: None))

        installed(monkeypatch, plugins=[PluginEntryPoint("p", lambda: register)])
        group = click.Group()

        cli.load_plugins(group)

        assert sorted(group.commands) == ["plugged"]

    def test_skips_a_plugin_that_fails_to_load(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        def explode() -> typing.Any:
            raise RuntimeError("broken plugin")

        installed(monkeypatch, plugins=[PluginEntryPoint("bad", explode)])
        group = click.Group()

        with caplog.at_level(logging.WARNING, logger="kupala.cli"):
            cli.load_plugins(group)

        assert group.commands == {}
        assert "which failed to load: broken plugin" in caplog.text

    def test_skips_a_plugin_that_is_a_command(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        """A command is callable, so calling one would run it instead of registering it."""

        command = click.Command(name="plugged", callback=lambda: None)
        installed(monkeypatch, plugins=[PluginEntryPoint("odd", lambda: command)])
        group = click.Group()

        with caplog.at_level(logging.WARNING, logger="kupala.cli"):
            cli.load_plugins(group)

        assert group.commands == {}
        assert "expected a callable taking the root group, got Command" in caplog.text

    def test_skips_a_plugin_that_is_not_callable(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        installed(monkeypatch, plugins=[PluginEntryPoint("odd", lambda: "nope")])
        group = click.Group()

        with caplog.at_level(logging.WARNING, logger="kupala.cli"):
            cli.load_plugins(group)

        assert group.commands == {}
        assert "expected a callable taking the root group, got str" in caplog.text

    def test_skips_a_plugin_that_raises_while_registering(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        def register(group: click.Group) -> None:
            raise RuntimeError("bad registration")

        installed(monkeypatch, plugins=[PluginEntryPoint("bad", lambda: register)])
        group = click.Group()

        with caplog.at_level(logging.WARNING, logger="kupala.cli"):
            cli.load_plugins(group)

        assert group.commands == {}
        assert "which failed while registering: bad registration" in caplog.text


class TestBuildCli:
    def test_registers_plugin_and_application_commands(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def register(group: click.Group) -> None:
            group.add_command(click.Command(name="plugged", callback=lambda: None))

        installed(monkeypatch, plugins=[PluginEntryPoint("p", lambda: register)])
        app = make_app(commands=[click.Command(name="owned", callback=lambda: None)])

        assert sorted(cli.build_cli(app).commands) == ["owned", "plugged"]

    def test_registers_plugin_commands_without_an_application(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def register(group: click.Group) -> None:
            group.add_command(click.Command(name="plugged", callback=lambda: None))

        installed(monkeypatch, plugins=[PluginEntryPoint("p", lambda: register)])

        assert sorted(cli.build_cli(None).commands) == ["plugged"]

    def test_an_application_command_wins_a_name_a_plugin_took(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """An application is closer to the developer than anything they merely installed."""

        plugin_command = click.Command(name="shared", callback=lambda: None)
        owned = click.Command(name="shared", callback=lambda: None)
        installed(monkeypatch, plugins=[PluginEntryPoint("p", lambda: lambda group: group.add_command(plugin_command))])

        assert cli.build_cli(make_app(commands=[owned])).commands == {"shared": owned}

    def test_carries_the_application_on_a_context_object(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Commands read the invocation off a dataclass, so it can grow without changing signatures."""

        installed(monkeypatch)
        app = make_app()
        seen: list[typing.Any] = []

        group = cli.build_cli(app)
        group.add_command(click.Command(name="peek", callback=lambda: seen.append(click.get_current_context().obj)))
        group.main(args=["peek"], standalone_mode=False)

        assert seen == [cli.CliContext(app=app)]

    def test_builds_a_fresh_group_for_every_invocation(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A group outliving one invocation would carry the previous application's commands into the next."""

        installed(monkeypatch)
        first = cli.build_cli(make_app(commands=[click.Command(name="owned", callback=lambda: None)]))

        assert "owned" in first.commands
        assert cli.build_cli(None).commands == {}


class TestUsageError:
    def test_carries_the_hint_as_a_note(self) -> None:
        error = commands_module.UsageError("It went wrong.", "Try the other thing.")

        assert error.message == "It went wrong."
        assert error.__notes__ == ["hint: Try the other thing."]

    def test_renders_the_message_above_every_note(self) -> None:
        """Click prints format_message() and never the notes, so they have to be folded in."""

        error = commands_module.UsageError("It went wrong.", "Try the other thing.")
        error.add_note("see: https://example.test")

        assert error.format_message() == "It went wrong.\nhint: Try the other thing.\nsee: https://example.test"


class TestCurrentApplication:
    def test_reads_the_application_off_the_root_context(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """`build_cli` puts the application on the root context object; this pins the two together."""

        installed(monkeypatch)
        app = make_app()
        seen: list[Kupala] = []

        group = cli.build_cli(app)
        group.add_command(
            click.Command(name="peek", callback=lambda: seen.append(commands_module.current_application()))
        )
        group.main(args=["peek"], standalone_mode=False)

        assert seen == [app]

    def test_reports_a_context_that_loaded_no_application(self) -> None:
        with (
            click.Context(click.Command("orphan"), obj=cli.CliContext(app=None)),
            pytest.raises(click.UsageError, match="needs an application"),
        ):
            commands_module.current_application()

    def test_reports_a_group_kupala_never_built(self) -> None:
        """A Kupala command added to someone else's group has no context object to read at all."""

        with click.Context(click.Command("orphan")), pytest.raises(click.UsageError, match="needs an application"):
            commands_module.current_application()

    def test_names_the_variable_that_would_have_loaded_one(self) -> None:
        """The hint repeats the variable as a literal, so this pins the two together."""

        with click.Context(click.Command("orphan")), pytest.raises(click.UsageError) as caught:
            commands_module.current_application()

        assert cli.APP_ENV_VAR in caught.value.format_message()


class TestCommands:
    def test_collects_definitions(self) -> None:
        commands = commands_module.Commands()

        @commands.command("one")
        def one() -> None: ...

        @commands.command()
        def two() -> None: ...

        assert [definition.name for definition in commands.definitions] == ["one", None]

    def test_derives_a_name_from_the_function(self) -> None:
        commands = commands_module.Commands()

        @commands.command()
        def do_something() -> None: ...

        assert [command.name for command in commands.compile()] == ["do-something"]

    def test_keeps_the_click_parameters_of_the_original_function(self) -> None:
        commands = commands_module.Commands()

        @commands.command("build")
        @click.option("--target", default="all")
        def build(target: str) -> None: ...

        assert [parameter.name for parameter in commands.compile()[0].params] == ["target"]

    def test_compiles_the_same_definition_more_than_once(self) -> None:
        """Click consumes the decorated parameters destructively, so compiling twice must still work."""

        commands = commands_module.Commands()

        @commands.command("build")
        @click.option("--target", default="all")
        def build(target: str) -> None: ...

        assert [parameter.name for parameter in commands.compile()[0].params] == ["target"]
        assert [parameter.name for parameter in commands.compile()[0].params] == ["target"]

    def test_accepts_a_definition_built_elsewhere(self) -> None:
        """An extension can assemble a definition itself rather than going through the decorator."""

        commands = commands_module.Commands()
        commands.add(
            commands_module.CommandDefinition(name="one", fn=lambda: None, with_lifespan=True, attrs={}),
        )

        assert [command.name for command in commands.compile()] == ["one"]

    def test_passes_extra_attributes_to_click(self) -> None:
        commands = commands_module.Commands()

        @commands.command("build", help="Build the thing.")
        def build() -> None: ...

        assert commands.compile()[0].help == "Build the thing."

    def test_records_the_lifespan_choice(self) -> None:
        commands = commands_module.Commands()

        @commands.command("online")
        def online() -> None: ...

        @commands.command("offline", with_lifespan=False)
        def offline() -> None: ...

        assert [definition.with_lifespan for definition in commands.definitions] == [True, False]


class TestCommandInvocation:
    def test_fills_click_parameters_and_dependencies_together(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        installed(monkeypatch)
        commands = commands_module.Commands()

        @commands.command("show")
        @click.option("--label", default="total")
        def show(label: str, currency: Currency) -> None:
            click.echo(f"{label} {currency}")

        app = make_app(commands=commands)

        assert app.cli(["show", "--label", "price"]) == 0
        assert capsys.readouterr().out == "price EUR\n"

    def test_injects_a_parameter_click_declares_but_never_passes(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """An expose_value=False option is click's in name only, so the injector still has to fill it."""

        installed(monkeypatch)
        commands = commands_module.Commands()

        @commands.command("show")
        @click.option("--currency", expose_value=False)
        def show(currency: Currency) -> None:
            click.echo(currency)

        app = make_app(commands=commands)

        assert app.cli(["show"]) == 0
        assert capsys.readouterr().out == "EUR\n"

    def test_injects_the_application_itself(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The application is bound on the injection scope, so a command asks for it by type."""

        installed(monkeypatch)
        commands = commands_module.Commands()

        @commands.command("whoami")
        def whoami(app: Kupala) -> None:
            click.echo(f"{app.name} {len(app.commands)}")

        app = make_app(commands=commands)

        assert app.cli(["whoami"]) == 0
        assert capsys.readouterr().out == f"{app.name} 1\n"

    def test_reads_state_the_lifespan_contributed(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        installed(monkeypatch)
        commands = commands_module.Commands()

        @commands.command("greet")
        def greet(greeting: Greeting) -> None:
            click.echo(greeting)

        app = make_app(commands=commands, greeting="hello")

        assert app.cli(["greet"]) == 0
        assert capsys.readouterr().out == "hello\n"

    def test_runs_an_async_command(self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        installed(monkeypatch)
        commands = commands_module.Commands()

        @commands.command("async-greet")
        async def greet(greeting: Greeting) -> None:
            click.echo(greeting)

        app = make_app(commands=commands, greeting="async hello")

        assert app.cli(["async-greet"]) == 0
        assert capsys.readouterr().out == "async hello\n"

    def test_a_command_can_opt_out_of_the_lifespan(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A command that repairs a broken deployment cannot depend on that deployment starting."""

        installed(monkeypatch)
        started: list[str] = []
        commands = commands_module.Commands()

        @commands.command("offline", with_lifespan=False)
        def offline() -> None:
            click.echo("no lifespan")

        @contextlib.asynccontextmanager
        async def lifespan(app: Kupala) -> typing.AsyncGenerator[dict[str, typing.Any]]:  # pragma: no cover
            started.append("started")
            yield {}

        app = Kupala(__name__, routes=Routes(), commands=commands, lifespans=[lifespan])

        assert app.cli(["offline"]) == 0
        assert capsys.readouterr().out == "no lifespan\n"
        assert started == []

    def test_a_command_without_an_application_is_a_usage_error(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """An extension's command is registered with or without an application; needing one is its own error."""

        commands = commands_module.Commands()

        @commands.command("orphan")
        def orphan(app: Kupala) -> None: ...  # pragma: no cover - the application is missing, so it never runs

        command = commands.compile()[0]
        installed(monkeypatch, plugins=[PluginEntryPoint("p", lambda: lambda group: group.add_command(command))])

        assert cli.main(["orphan"]) == 2
        assert "needs an application and none was loaded" in capsys.readouterr().err


class TestCommandDiscovery:
    def test_lists_application_commands(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        installed(monkeypatch)
        app = make_app(commands=[click.Command(name="owned", callback=lambda: None)])

        assert cli.main(["--help"], app=app) == 0
        assert "owned" in capsys.readouterr().out

    def test_help_works_without_an_application(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The CLI is installed machine-wide, so it has to work in any directory."""

        installed(monkeypatch)

        assert cli.main(["--help"]) == 0
        assert "Kupala command line interface" in capsys.readouterr().out

    def test_the_variable_selects_the_application(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        installed(monkeypatch)
        monkeypatch.syspath_prepend(str(tmp_path))
        module = write_app_module(tmp_path)
        monkeypatch.setenv(cli.APP_ENV_VAR, f"{module}:app")

        assert cli.main(["sample"]) == 0
        assert capsys.readouterr().out == "sample ran\n"

    def test_an_installed_project_selects_the_application(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.syspath_prepend(str(tmp_path))
        module = write_app_module(tmp_path)
        installed(monkeypatch, apps=[AppEntryPoint(f"{module}:app")])

        assert cli.main(["sample"]) == 0
        assert capsys.readouterr().out == "sample ran\n"

    def test_an_explicit_application_skips_discovery(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Kupala.cli() hands the application over, so a stale variable is never consulted."""

        installed(monkeypatch)
        monkeypatch.setenv(cli.APP_ENV_VAR, "never.imported:app")
        app = make_app(commands=[click.Command(name="owned", callback=lambda: click.echo("owned ran"))])

        assert app.cli(["owned"]) == 0
        assert capsys.readouterr().out == "owned ran\n"

    def test_reads_the_arguments_from_the_command_line_by_default(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.syspath_prepend(str(tmp_path))
        module = write_app_module(tmp_path)
        installed(monkeypatch, apps=[AppEntryPoint(f"{module}:app")])
        monkeypatch.setattr(sys, "argv", ["kupala", "sample"])

        assert cli.main() == 0
        assert capsys.readouterr().out == "sample ran\n"

    def test_an_unknown_command_is_a_usage_error(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        installed(monkeypatch)

        assert cli.main(["nope"]) == 2
        assert "No such command" in capsys.readouterr().err

    def test_an_application_that_does_not_import_is_reported(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        installed(monkeypatch)
        monkeypatch.setenv(cli.APP_ENV_VAR, "never.imported:app")

        assert cli.main(["--help"]) == 2
        assert "Cannot import" in capsys.readouterr().err


class TestMain:
    def test_reports_a_click_exception(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        def fail() -> None:
            raise click.ClickException("it went wrong")

        installed(monkeypatch)
        app = make_app(commands=[click.Command(name="fail", callback=fail)])

        assert app.cli(["fail"]) == 1
        assert "it went wrong" in capsys.readouterr().err

    def test_maps_an_interrupt_to_the_signal_exit_code(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        def interrupt() -> None:
            raise KeyboardInterrupt

        installed(monkeypatch)
        app = make_app(commands=[click.Command(name="interrupt", callback=interrupt)])

        assert app.cli(["interrupt"]) == 130
        assert "Aborted." in capsys.readouterr().err

    def test_maps_an_abort_to_a_plain_failure(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        def abort() -> None:
            raise click.Abort

        installed(monkeypatch)
        app = make_app(commands=[click.Command(name="abort", callback=abort)])

        assert app.cli(["abort"]) == 1
        assert "Aborted." in capsys.readouterr().err

    def test_passes_through_an_explicit_exit_code(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def leave() -> None:
            raise click.exceptions.Exit(3)

        installed(monkeypatch)
        app = make_app(commands=[click.Command(name="leave", callback=leave)])

        assert app.cli(["leave"]) == 3

    def test_succeeds_when_a_command_returns_nothing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        installed(monkeypatch)
        app = make_app(commands=[click.Command(name="quiet", callback=lambda: None)])

        assert app.cli(["quiet"]) == 0
