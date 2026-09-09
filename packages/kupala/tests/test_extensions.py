import contextlib
import typing

import click
import jinja2
from starlette.testclient import TestClient

from kupala.applications import Kupala
from kupala.binders import ModelBinder
from kupala.commands import Commands
from kupala.error_handlers import server_error_handler
from kupala.extensions import AppBuilder, Extension
from kupala.requests import Request
from kupala.responses import Response
from kupala.routing import Routes
from kupala.templates import Templates


class Failure(Exception):
    """Raised by a route so an error handler has something to catch."""


class TestAppBuilder:
    """Every field is a container extensions append to, so two of them never overwrite each other."""

    def test_starts_empty(self) -> None:
        builder = AppBuilder()

        assert list(builder.routes) == []
        assert builder.lifespans == []
        assert builder.template_loaders == []
        assert builder.template_globals == {}
        assert builder.template_filters == {}
        assert builder.model_binders == []
        assert builder.context_processors == []
        assert builder.error_handlers == {}

    def test_two_extensions_accumulate(self) -> None:
        first_binder = typing.cast(ModelBinder, object())
        second_binder = typing.cast(ModelBinder, object())

        class First:
            def install(self, builder: AppBuilder) -> None:
                builder.template_globals["first"] = 1
                builder.model_binders.append(first_binder)

        class Second:
            def install(self, builder: AppBuilder) -> None:
                builder.template_globals["second"] = 2
                builder.model_binders.append(second_binder)

        builder = AppBuilder()
        for extension in (First(), Second()):
            extension.install(builder)

        assert builder.template_globals == {"first": 1, "second": 2}
        assert builder.model_binders == [first_binder, second_binder]


class TestInstallsExtensions:
    def test_contributes_routes(self) -> None:
        class Ext:
            def install(self, builder: AppBuilder) -> None:
                @builder.routes.get("/from-extension")
                async def view(request: Request) -> Response:
                    return Response("extension")

        app = Kupala("tests", routes=Routes(), extensions=[Ext()])

        with TestClient(app) as client:
            assert client.get("/from-extension").text == "extension"

    def test_contributes_commands(self) -> None:
        commands = Commands()

        class Ext:
            def install(self, builder: AppBuilder) -> None:
                @builder.commands.command("from-extension")
                def command() -> None:
                    click.echo("ran")  # pragma: no cover

        app = Kupala("tests", routes=Routes(), commands=commands, extensions=[Ext()])

        assert [command.name for command in app.commands] == ["from-extension"]

    def test_contributes_a_lifespan(self) -> None:
        events: list[str] = []

        @contextlib.asynccontextmanager
        async def lifespan(app: Kupala) -> typing.AsyncGenerator[None]:
            events.append("up")
            yield None
            events.append("down")

        class Ext:
            def install(self, builder: AppBuilder) -> None:
                builder.lifespans.append(lifespan)

        with TestClient(Kupala("tests", routes=Routes(), extensions=[Ext()])):
            assert events == ["up"]

        assert events == ["up", "down"]

    def test_contributes_templates(self) -> None:
        class Ext:
            def install(self, builder: AppBuilder) -> None:
                builder.template_loaders.append(jinja2.DictLoader({"ext.html": "{{ 'hi'|shout }} {{ site }}"}))
                builder.template_globals["site"] = "Acme"
                builder.template_filters["shout"] = str.upper

        templates = Templates()
        Kupala("tests", routes=Routes(), templates=templates, extensions=[Ext()])

        assert templates.render("ext.html") == "HI Acme"

    def test_contributes_a_model_binder(self) -> None:
        binder = typing.cast(typing.Any, object())

        class Ext:
            def install(self, builder: AppBuilder) -> None:
                builder.model_binders.append(binder)

        app = Kupala("tests", routes=Routes(), extensions=[Ext()])

        assert app.model_binders[-1] is binder

    def test_an_extension_template_outranks_a_framework_one(self) -> None:
        class Ext:
            def install(self, builder: AppBuilder) -> None:
                builder.template_loaders.append(jinja2.DictLoader({"openapi/swagger.html.j2": "extension"}))

        templates = Templates()
        Kupala("tests", routes=Routes(), templates=templates, extensions=[Ext()])

        assert templates.render("openapi/swagger.html.j2") == "extension"

    def test_an_application_template_outranks_an_extension_one(self) -> None:
        class Ext:
            def install(self, builder: AppBuilder) -> None:
                builder.template_loaders.append(jinja2.DictLoader({"page.html": "extension"}))

        templates = Templates(loaders=[jinja2.DictLoader({"page.html": "application"})])
        Kupala("tests", routes=Routes(), templates=templates, extensions=[Ext()])

        assert templates.render("page.html") == "application"


class TestExtensionErrorHandlers:
    def test_contributes_an_error_handler(self) -> None:
        async def handle(request: Request, exc: Exception) -> Response:
            return Response("handled", status_code=418)

        class Ext:
            def install(self, builder: AppBuilder) -> None:
                builder.error_handlers[Failure] = handle

        routes = Routes()

        @routes.get("/boom")
        async def boom(request: Request) -> Response:
            raise Failure()

        app = Kupala("tests", routes=routes, extensions=[Ext()])

        with TestClient(app) as client:
            assert client.get("/boom").status_code == 418

    def test_the_application_overrides_an_extension_handler(self) -> None:
        async def from_extension(request: Request, exc: Exception) -> Response:
            return Response("extension", status_code=418)  # pragma: no cover

        async def from_application(request: Request, exc: Exception) -> Response:
            return Response("application", status_code=419)

        class Ext:
            def install(self, builder: AppBuilder) -> None:
                builder.error_handlers[Failure] = from_extension

        routes = Routes()

        @routes.get("/boom")
        async def boom(request: Request) -> Response:
            raise Failure()

        app = Kupala("tests", routes=routes, error_handlers={Failure: from_application}, extensions=[Ext()])

        with TestClient(app) as client:
            assert client.get("/boom").text == "application"

    def test_a_catch_all_handler_cannot_slip_past_the_server_error_split(self) -> None:
        # a handler for Exception left in the map would match every error by MRO and answer before
        # ServerErrorMiddleware could re-raise it for the server to log
        async def catch_all(request: Request, exc: Exception) -> Response:
            return Response("caught", status_code=500)  # pragma: no cover

        class Ext:
            def install(self, builder: AppBuilder) -> None:
                builder.error_handlers[Exception] = catch_all

        app = Kupala("tests", routes=Routes(), extensions=[Ext()])

        assert app.server_error_handler is catch_all
        assert Exception not in app.error_handlers


class TestExtensionProtocol:
    def test_a_plain_object_with_install_satisfies_it(self) -> None:
        class Ext:
            def install(self, builder: AppBuilder) -> None:
                builder.template_globals["installed"] = True

        extension: Extension = Ext()
        builder = AppBuilder()
        extension.install(builder)

        assert builder.template_globals == {"installed": True}


def test_no_extensions_leaves_the_defaults_alone() -> None:
    app = Kupala("tests", routes=Routes())

    assert app.server_error_handler is server_error_handler
    assert list(app.routes) == []
