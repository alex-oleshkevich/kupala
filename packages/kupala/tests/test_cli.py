import contextlib
import importlib.metadata
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


class FakeEntryPoint:
    """Stands in for an installed package contributing a command."""

    def __init__(self, name: str, loader: typing.Callable[[], typing.Any]) -> None:
        self.name = name
        self._loader = loader

    def load(self) -> typing.Any:
        return self._loader()


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
        yield {"greeting": greeting, "started": True}

    return Kupala(__name__, routes=Routes(), commands=commands, lifespans=[lifespan])


def no_plugins(monkeypatch: pytest.MonkeyPatch) -> None:
    """Detach the test from whatever the environment happens to have installed."""

    monkeypatch.setattr(importlib.metadata, "entry_points", lambda **_: [])


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

        with pytest.raises(click.UsageError, match="not a Kupala application"):
            cli.import_app(f"{module}:NOT_AN_APP", cli.APP_ENV_VAR)

    def test_lets_the_application_own_import_error_through(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A dependency missing inside the application is the application's bug, not a usage error."""

        monkeypatch.syspath_prepend(str(tmp_path))
        (tmp_path / "broken_import.py").write_text("import kupala_no_such_dependency\n")

        with pytest.raises(ModuleNotFoundError):
            cli.import_app("broken_import:app", cli.APP_ENV_VAR)


class TestTakeAppOption:
    @pytest.mark.parametrize(
        ("args", "pointer", "remaining"),
        [
            (["--app", "demo.app:app", "run"], "demo.app:app", ["run"]),
            (["--app=demo.app:app", "run"], "demo.app:app", ["run"]),
            (["--app=", "run"], "", ["run"]),
            (["run"], None, ["run"]),
            ([], None, []),
            (["--version"], None, ["--version"]),
            (["--app", "one:app", "--app=two:app", "run"], "two:app", ["run"]),
        ],
    )
    def test_takes_the_option_and_leaves_the_rest(
        self, args: list[str], pointer: str | None, remaining: list[str]
    ) -> None:
        assert cli.take_app_option(args) == (pointer, remaining)

    @pytest.mark.parametrize(
        "args",
        [["run", "--app", "other:app"], ["--", "--app", "other:app"]],
    )
    def test_stops_at_the_subcommand(self, args: list[str]) -> None:
        """A subcommand with an --app option of its own has to keep it."""

        assert cli.take_app_option(args) == (None, args)

    def test_reports_the_option_without_a_value(self) -> None:
        with pytest.raises(click.UsageError, match="needs a value"):
            cli.take_app_option(["--app"])


class TestResolveApplication:
    def test_the_option_beats_everything(self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.syspath_prepend(str(tmp_path))
        module = write_app_module(tmp_path)
        monkeypatch.setenv(cli.APP_ENV_VAR, "never.imported:app")

        assert cli.resolve_application(f"{module}:app", make_app()) is not None

    def test_an_application_handed_in_beats_the_variable(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(cli.APP_ENV_VAR, "never.imported:app")
        app = make_app()

        assert cli.resolve_application(None, app) is app

    def test_imports_the_application_the_variable_names(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.syspath_prepend(str(tmp_path))
        module = write_app_module(tmp_path)
        monkeypatch.setenv(cli.APP_ENV_VAR, f"{module}:app")

        assert cli.resolve_application(None, None) is not None

    def test_finds_nothing_when_nothing_names_one(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv(cli.APP_ENV_VAR, raising=False)

        assert cli.resolve_application(None, None) is None

    def test_a_variable_that_does_not_import_is_an_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Setting it is a statement of intent, so failing to import one is loud, never a silent miss."""

        monkeypatch.setenv(cli.APP_ENV_VAR, "never.imported:app")

        with pytest.raises(click.UsageError, match="Cannot import"):
            cli.resolve_application(None, None)

    def test_never_puts_the_working_directory_on_the_import_path(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Running the CLI inside an untrusted checkout must not make that checkout importable."""

        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv(cli.APP_ENV_VAR, raising=False)
        write_app_module(tmp_path)
        before = list(sys.path)

        assert cli.resolve_application(None, None) is None
        assert sys.path == before


class TestLoadPlugins:
    def test_collects_commands_from_the_entry_point_group(self, monkeypatch: pytest.MonkeyPatch) -> None:
        command = click.Command(name="plugged", callback=lambda: None)
        monkeypatch.setattr(importlib.metadata, "entry_points", lambda **_: [FakeEntryPoint("p", lambda: command)])

        assert cli.load_plugins() == {"plugged": command}

    def test_falls_back_to_the_entry_point_name(self, monkeypatch: pytest.MonkeyPatch) -> None:
        command = click.Command(name=None, callback=lambda: None)
        monkeypatch.setattr(importlib.metadata, "entry_points", lambda **_: [FakeEntryPoint("named", lambda: command)])

        assert cli.load_plugins() == {"named": command}

    def test_skips_a_plugin_that_fails_to_load(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def explode() -> typing.Any:
            raise RuntimeError("broken plugin")

        monkeypatch.setattr(importlib.metadata, "entry_points", lambda **_: [FakeEntryPoint("bad", explode)])

        assert cli.load_plugins() == {}

    def test_skips_a_plugin_that_is_not_a_command(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(importlib.metadata, "entry_points", lambda **_: [FakeEntryPoint("odd", lambda: "nope")])

        assert cli.load_plugins() == {}


class TestContributedCommands:
    def test_application_commands_win_a_name_collision(self, monkeypatch: pytest.MonkeyPatch) -> None:
        plugin = click.Command(name="shared", callback=lambda: None)
        owned = click.Command(name="shared", callback=lambda: None)
        monkeypatch.setattr(importlib.metadata, "entry_points", lambda **_: [FakeEntryPoint("p", lambda: plugin)])

        assert cli.contributed_commands(make_app(commands=[owned])) == {"shared": owned}

    def test_lists_plugin_commands_without_an_application(self, monkeypatch: pytest.MonkeyPatch) -> None:
        plugin = click.Command(name="plugged", callback=lambda: None)
        monkeypatch.setattr(importlib.metadata, "entry_points", lambda **_: [FakeEntryPoint("p", lambda: plugin)])

        assert cli.contributed_commands(None) == {"plugged": plugin}

    def test_ignores_an_application_command_without_a_name(self, monkeypatch: pytest.MonkeyPatch) -> None:
        no_plugins(monkeypatch)

        assert cli.contributed_commands(make_app(commands=[click.Command(name=None, callback=lambda: None)])) == {}


class TestBuildCli:
    def test_registers_plugin_and_application_commands(self, monkeypatch: pytest.MonkeyPatch) -> None:
        plugin = click.Command(name="plugged", callback=lambda: None)
        monkeypatch.setattr(importlib.metadata, "entry_points", lambda **_: [FakeEntryPoint("p", lambda: plugin)])
        app = make_app(commands=[click.Command(name="owned", callback=lambda: None)])

        assert sorted(cli.build_cli(app).commands) == ["owned", "plugged"]

    def test_registers_a_plugin_under_its_entry_point_name(self, monkeypatch: pytest.MonkeyPatch) -> None:
        command = click.Command(name=None, callback=lambda: None)
        monkeypatch.setattr(importlib.metadata, "entry_points", lambda **_: [FakeEntryPoint("named", lambda: command)])

        assert sorted(cli.build_cli(None).commands) == ["named"]

    def test_builds_a_fresh_group_for_every_invocation(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A group outliving one invocation would carry the previous application's commands into the next."""

        no_plugins(monkeypatch)
        first = cli.build_cli(make_app(commands=[click.Command(name="owned", callback=lambda: None)]))

        assert "owned" in first.commands
        assert cli.build_cli(None).commands == {}

    def test_says_how_to_load_an_application_when_none_is_loaded(self, monkeypatch: pytest.MonkeyPatch) -> None:
        no_plugins(monkeypatch)
        epilog = cli.build_cli(None).epilog or ""

        assert cli.APP_ENV_VAR in epilog
        assert cli.APP_OPTION in epilog

    def test_documents_the_option_main_consumes_before_click_sees_it(self, monkeypatch: pytest.MonkeyPatch) -> None:
        no_plugins(monkeypatch)

        declared = {parameter.name: parameter for parameter in cli.build_cli(None).params}

        assert declared["app"].expose_value is False

    def test_says_nothing_extra_once_an_application_is_loaded(self, monkeypatch: pytest.MonkeyPatch) -> None:
        no_plugins(monkeypatch)

        assert cli.build_cli(make_app()).epilog is None


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

        assert [command.name for command in commands.compile()] == ["build"]
        assert commands.compile()[0].params[0].name == "target"


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
    def test_names_the_variable_that_would_have_loaded_one(self) -> None:
        """The hint repeats the variable as a literal, so this pins the two together."""

        with click.Context(click.Command("orphan")), pytest.raises(click.UsageError) as caught:
            commands_module.current_application()

        assert cli.APP_ENV_VAR in caught.value.format_message()


class TestCommandInvocation:
    def test_fills_click_parameters_and_dependencies_together(self, capsys: pytest.CaptureFixture[str]) -> None:
        commands = commands_module.Commands()

        @commands.command("show")
        @click.option("--label", default="total")
        def show(label: str, currency: Currency) -> None:
            click.echo(f"{label} {currency}")

        app = make_app(commands=commands)

        assert app.cli(["show", "--label", "price"]) == 0
        assert capsys.readouterr().out == "price EUR\n"

    def test_injects_the_application_itself(self, capsys: pytest.CaptureFixture[str]) -> None:
        """The application is bound on the injection scope, so a command asks for it by type."""

        commands = commands_module.Commands()

        @commands.command("whoami")
        def whoami(app: Kupala) -> None:
            click.echo(f"{app.name} {len(app.commands)}")

        app = make_app(commands=commands)

        assert app.cli(["whoami"]) == 0
        assert capsys.readouterr().out == f"{app.name} 1\n"

    def test_reads_state_the_lifespan_contributed(self, capsys: pytest.CaptureFixture[str]) -> None:
        commands = commands_module.Commands()

        @commands.command("greet")
        def greet(greeting: Greeting) -> None:
            click.echo(greeting)

        app = make_app(commands=commands, greeting="hello")

        assert app.cli(["greet"]) == 0
        assert capsys.readouterr().out == "hello\n"

    def test_runs_an_async_command(self, capsys: pytest.CaptureFixture[str]) -> None:
        commands = commands_module.Commands()

        @commands.command("async-greet")
        async def greet(greeting: Greeting) -> None:
            click.echo(greeting)

        app = make_app(commands=commands, greeting="async hello")

        assert app.cli(["async-greet"]) == 0
        assert capsys.readouterr().out == "async hello\n"

    def test_a_command_can_opt_out_of_the_lifespan(self, capsys: pytest.CaptureFixture[str]) -> None:
        commands = commands_module.Commands()

        @commands.command("offline", lifespan=False)
        def offline() -> None:
            click.echo("no lifespan")

        app = make_app(commands=commands)

        assert app.cli(["offline"]) == 0
        assert capsys.readouterr().out == "no lifespan\n"

    def test_a_plugin_command_without_an_application_is_a_usage_error(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """An extension's command is registered with or without an application; needing one is its own error."""

        monkeypatch.delenv(cli.APP_ENV_VAR, raising=False)
        commands = commands_module.Commands()

        @commands.command("orphan")
        def orphan(app: Kupala) -> None: ...  # pragma: no cover - the application is missing, so it never runs

        monkeypatch.setattr(
            importlib.metadata,
            "entry_points",
            lambda **_: [FakeEntryPoint("p", lambda: commands.compile()[0])],
        )

        assert cli.main(["orphan"]) == 2
        assert "needs an application and none was loaded" in capsys.readouterr().err


class TestCommandDiscovery:
    def test_lists_application_commands(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        no_plugins(monkeypatch)
        app = make_app(commands=[click.Command(name="owned", callback=lambda: None)])

        assert cli.main(["--help"], app=app) == 0
        assert "owned" in capsys.readouterr().out

    def test_help_works_without_an_application(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The CLI is installed machine-wide, so it has to work in any directory."""

        no_plugins(monkeypatch)
        monkeypatch.delenv(cli.APP_ENV_VAR, raising=False)

        assert cli.main(["--help"]) == 0
        assert "Kupala command line interface" in capsys.readouterr().out

    def test_the_environment_selects_the_application(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        no_plugins(monkeypatch)
        monkeypatch.syspath_prepend(str(tmp_path))
        module = write_app_module(tmp_path)
        monkeypatch.setenv(cli.APP_ENV_VAR, f"{module}:app")

        assert cli.main(["sample"]) == 0
        assert capsys.readouterr().out == "sample ran\n"

    def test_an_explicit_application_skips_the_environment(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Kupala.cli() hands the application over, so a stale variable is never consulted."""

        no_plugins(monkeypatch)
        monkeypatch.setenv(cli.APP_ENV_VAR, "never.imported:app")
        app = make_app(commands=[click.Command(name="owned", callback=lambda: click.echo("owned ran"))])

        assert app.cli(["owned"]) == 0
        assert capsys.readouterr().out == "owned ran\n"

    def test_the_option_selects_the_application(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        no_plugins(monkeypatch)
        monkeypatch.syspath_prepend(str(tmp_path))
        monkeypatch.setenv(cli.APP_ENV_VAR, "never.imported:app")
        module = write_app_module(tmp_path)

        assert cli.main([cli.APP_OPTION, f"{module}:app", "sample"]) == 0
        assert capsys.readouterr().out == "sample ran\n"

    def test_the_option_overrides_an_application_handed_in(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A manage.py in a repository with several applications can still point elsewhere."""

        no_plugins(monkeypatch)
        monkeypatch.syspath_prepend(str(tmp_path))
        module = write_app_module(tmp_path)
        app = make_app(commands=[click.Command(name="owned", callback=lambda: None)])

        assert app.cli([cli.APP_OPTION, f"{module}:app", "sample"]) == 0
        assert capsys.readouterr().out == "sample ran\n"

    def test_reads_the_arguments_from_the_command_line_by_default(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        no_plugins(monkeypatch)
        monkeypatch.syspath_prepend(str(tmp_path))
        module = write_app_module(tmp_path)
        monkeypatch.setattr(sys, "argv", ["kupala", cli.APP_OPTION, f"{module}:app", "sample"])

        assert cli.main() == 0
        assert capsys.readouterr().out == "sample ran\n"

    def test_an_unknown_command_is_a_usage_error(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        no_plugins(monkeypatch)
        monkeypatch.delenv(cli.APP_ENV_VAR, raising=False)

        assert cli.main(["nope"]) == 2
        assert "No such command" in capsys.readouterr().err

    def test_an_application_that_does_not_import_is_reported(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.setenv(cli.APP_ENV_VAR, "never.imported:app")

        assert cli.main(["--help"]) == 2
        assert "Cannot import" in capsys.readouterr().err


class TestMain:
    def test_reports_a_click_exception(self, capsys: pytest.CaptureFixture[str]) -> None:
        def fail() -> None:
            raise click.ClickException("it went wrong")

        app = make_app(commands=[click.Command(name="fail", callback=fail)])

        assert app.cli(["fail"]) == 1
        assert "it went wrong" in capsys.readouterr().err

    def test_maps_an_interrupt_to_the_signal_exit_code(self, capsys: pytest.CaptureFixture[str]) -> None:
        def interrupt() -> None:
            raise KeyboardInterrupt

        app = make_app(commands=[click.Command(name="interrupt", callback=interrupt)])

        assert app.cli(["interrupt"]) == 130
        assert "Aborted." in capsys.readouterr().err

    def test_maps_an_abort_to_a_plain_failure(self, capsys: pytest.CaptureFixture[str]) -> None:
        def abort() -> None:
            raise click.Abort

        app = make_app(commands=[click.Command(name="abort", callback=abort)])

        assert app.cli(["abort"]) == 1
        assert "Aborted." in capsys.readouterr().err

    def test_passes_through_an_explicit_exit_code(self, capsys: pytest.CaptureFixture[str]) -> None:
        def leave() -> None:
            raise click.exceptions.Exit(3)

        app = make_app(commands=[click.Command(name="leave", callback=leave)])

        assert app.cli(["leave"]) == 3
