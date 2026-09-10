import contextlib
import typing

import jinja2
import pytest
from starlette.exceptions import HTTPException
from starlette.testclient import TestClient

from kupala.applications import Kupala
from kupala.dependencies import INVOCATION_CONTEXT_KEY, Factory, FromState, InvocationContext, Value, constant
from kupala.middleware import CallNext, WebSocketCallNext
from kupala.requests import Request
from kupala.responses import Response, StreamingResponse, response
from kupala.routing import Routes
from kupala.templates import Templates
from kupala.websockets import WebSocket

type _Greeting = typing.Annotated[str, Value("real")]
type _Uncached = typing.Annotated[str, Factory(lambda: "real", cache=False)]


class TestDependencyLifetime:
    def test_closes_generator_dependencies_after_the_response(self) -> None:
        events: list[str] = []

        def make_resource() -> typing.Iterator[str]:
            yield "demovalue"
            events.append("closed")

        routes = Routes()

        @routes.get("/")
        async def index(resource: typing.Annotated[str, Factory(make_resource)]) -> Response:
            events.append("handled")
            return Response(resource)

        with TestClient(Kupala("tests", routes=routes)) as client:
            assert client.get("/").text == "demovalue"

        assert events == ["handled", "closed"]

    def test_keeps_the_dependency_alive_while_the_body_streams(self) -> None:
        events: list[str] = []

        def make_resource() -> typing.Iterator[str]:
            yield "demovalue"
            events.append("closed")

        routes = Routes()

        @routes.get("/")
        async def index(resource: typing.Annotated[str, Factory(make_resource)]) -> Response:
            def stream() -> typing.Iterator[str]:
                for chunk in ("first", "second"):
                    events.append(chunk)
                    yield f"{resource}:{chunk} "

            return StreamingResponse(stream())

        with TestClient(Kupala("tests", routes=routes)) as client:
            assert client.get("/").text == "demovalue:first demovalue:second "

        # teardown must come last, or a streaming body would read a released resource
        assert events == ["first", "second", "closed"]

    def test_lets_an_unhandled_error_reach_the_dependency(self) -> None:
        events: list[str] = []

        def make_resource() -> typing.Iterator[str]:
            try:
                yield "demovalue"
            except RuntimeError:
                events.append("saw error")
                raise
            finally:
                events.append("closed")

        routes = Routes()

        @routes.get("/")
        async def index(resource: typing.Annotated[str, Factory(make_resource)]) -> Response:
            raise RuntimeError("boom")

        app = Kupala("tests", routes=routes)
        with TestClient(app, raise_server_exceptions=False) as client:
            assert client.get("/").status_code == 500

        # ServerErrorMiddleware sends the 500 and then re-raises, so the error does reach the exit stack
        assert events == ["saw error", "closed"]

    def test_hides_a_handled_error_from_the_dependency(self) -> None:
        events: list[str] = []

        def make_resource() -> typing.Iterator[str]:
            try:
                yield "demovalue"
            except HTTPException:  # pragma: no cover - the handler answers before the stack unwinds
                events.append("saw error")
                raise
            finally:
                events.append("closed")

        routes = Routes()

        @routes.get("/")
        async def index(resource: typing.Annotated[str, Factory(make_resource)]) -> Response:
            raise HTTPException(409)

        with TestClient(Kupala("tests", routes=routes)) as client:
            assert client.get("/").status_code == 409

        assert events == ["closed"]

    def test_binds_the_application_itself(self) -> None:
        routes = Routes()

        @routes.get("/")
        async def index(app: Kupala) -> Response:
            return Response(app.name)

        with TestClient(Kupala("tests", routes=routes)) as client:
            assert client.get("/").text == "tests"


@pytest.fixture
def overridable_app() -> Kupala:
    """An app whose every endpoint reads a dependency the tests below replace."""

    routes = Routes()

    @routes.get("/greeting")
    async def greeting(greeting: _Greeting) -> Response:
        return Response(greeting)

    @routes.get("/uncached")
    async def uncached(value: _Uncached) -> Response:
        return Response(value)

    @routes.get("/who")
    async def who(request: Request) -> Response:
        # names the class actually injected, so a replaced Request is visible
        return Response(type(request).__name__)

    @routes.websocket("/ws")
    async def socket(websocket: WebSocket, greeting: _Greeting) -> None:
        await websocket.accept()
        await websocket.send_text(greeting)
        await websocket.close()

    return Kupala("tests", routes=routes)


@pytest.fixture
def overridable_client(overridable_app: Kupala) -> typing.Iterator[TestClient]:
    with TestClient(overridable_app) as client:
        yield client


class TestOverrideDependencies:
    def test_applies_inside_the_block_only(self, overridable_app: Kupala, overridable_client: TestClient) -> None:
        with overridable_app.override_dependencies({_Greeting: Value("fake")}):
            assert overridable_client.get("/greeting").text == "fake"

        assert overridable_client.get("/greeting").text == "real"

    def test_restores_after_an_error_inside_the_block(
        self, overridable_app: Kupala, overridable_client: TestClient
    ) -> None:
        with (
            pytest.raises(RuntimeError, match="boom"),
            overridable_app.override_dependencies({_Greeting: Value("fake")}),
        ):
            raise RuntimeError("boom")

        assert overridable_client.get("/greeting").text == "real"

    def test_nested_blocks_merge(self, overridable_app: Kupala, overridable_client: TestClient) -> None:
        with overridable_app.override_dependencies({_Greeting: Value("outer")}):
            with overridable_app.override_dependencies({_Uncached: Value("inner")}):
                assert overridable_client.get("/greeting").text == "outer"
                assert overridable_client.get("/uncached").text == "inner"

            # the inner block is gone, the outer one still stands
            assert overridable_client.get("/uncached").text == "real"
            assert overridable_client.get("/greeting").text == "outer"

    def test_replaces_a_dependency_that_never_caches(
        self, overridable_app: Kupala, overridable_client: TestClient
    ) -> None:
        # a cache=False factory has no cache entry to seed, so only an override can reach it
        with overridable_app.override_dependencies({_Uncached: Value("fake")}):
            assert overridable_client.get("/uncached").text == "fake"

    def test_wins_over_a_binding_the_router_makes(
        self, overridable_app: Kupala, overridable_client: TestClient
    ) -> None:
        # the router binds the real Request on every request, and the override still takes precedence
        StubRequest = type("StubRequest", (), {})

        with overridable_app.override_dependencies({Request: Value(StubRequest())}):
            assert overridable_client.get("/who").text == "StubRequest"

        assert overridable_client.get("/who").text == "Request"

    def test_replaces_a_dependency_with_a_factory(
        self, overridable_app: Kupala, overridable_client: TestClient
    ) -> None:
        # overrides are bindings rather than plain values, so a double can bring its own cleanup
        events: list[str] = []

        def fake_greeting() -> typing.Iterator[str]:
            yield "fake"
            events.append("released")

        with overridable_app.override_dependencies({_Greeting: Factory(fake_greeting)}):
            assert overridable_client.get("/greeting").text == "fake"
            assert events == ["released"]

    def test_reaches_websocket_endpoints(self, overridable_app: Kupala, overridable_client: TestClient) -> None:
        with (
            overridable_app.override_dependencies({_Greeting: Value("fake")}),
            overridable_client.websocket_connect("/ws") as websocket,
        ):
            assert websocket.receive_text() == "fake"


class TestInvocationState:
    def test_injects_what_a_middleware_left_on_request_state(self) -> None:
        async def attach(request: Request, call_next: CallNext) -> Response:
            request.state.db = "session"
            return await call_next(request)

        routes = Routes()

        @routes.get("/")
        async def index(db: typing.Annotated[str, FromState(lambda ctx, state: state.db)]) -> Response:
            return Response(db)

        with TestClient(Kupala("tests", routes=routes, middleware=[attach])) as client:
            assert client.get("/").text == "session"

    def test_injects_state_into_websocket_endpoints(self) -> None:
        async def attach(websocket: WebSocket, call_next: WebSocketCallNext) -> None:
            websocket.state.db = "session"
            await call_next(websocket)

        routes = Routes()

        @routes.websocket("/ws")
        async def socket(
            websocket: WebSocket, db: typing.Annotated[str, FromState(lambda ctx, state: state.db)]
        ) -> None:
            await websocket.accept()
            await websocket.send_text(db)
            await websocket.close()

        app = Kupala("tests", routes=routes, websocket_middleware=[attach])
        with TestClient(app) as client, client.websocket_connect("/ws") as websocket:
            assert websocket.receive_text() == "session"

    def test_shares_one_dict_with_starlette(self) -> None:
        # the injector and request.state must see each other's writes, not two copies
        routes = Routes()

        @routes.get("/")
        async def index(request: Request) -> Response:
            context: InvocationContext = request.scope[INVOCATION_CONTEXT_KEY]
            request.state.written_by_starlette = "a"
            context.state.written_by_injector = "b"
            return Response(f"{context.state.written_by_starlette}{request.state.written_by_injector}")

        with TestClient(Kupala("tests", routes=routes)) as client:
            assert client.get("/").text == "ab"

    def test_injects_what_the_lifespan_provided(self) -> None:
        # the reason FromState exists: one object built at startup, injected into every request
        @contextlib.asynccontextmanager
        async def open_catalog(app: Kupala) -> typing.AsyncGenerator[dict[str, typing.Any]]:
            yield {"catalog": "loaded once"}

        routes = Routes()

        @routes.get("/")
        async def index(catalog: typing.Annotated[str, FromState(lambda ctx, state: state.catalog)]) -> Response:
            return Response(catalog)

        with TestClient(Kupala("tests", routes=routes, lifespans=[open_catalog])) as client:
            assert client.get("/").text == "loaded once"
            assert client.get("/").text == "loaded once"

    def test_a_state_dependency_can_be_overridden(self) -> None:
        type Catalog = typing.Annotated[str, FromState(lambda ctx, state: state.catalog)]

        routes = Routes()

        @routes.get("/")
        async def index(catalog: Catalog) -> Response:
            return Response(catalog)

        app = Kupala("tests", routes=routes)
        with TestClient(app) as client, app.override_dependencies({Catalog: Value("fake")}):
            # the selector never runs, so the missing state key is never reached
            assert client.get("/").text == "fake"


class TestLifespans:
    def test_merges_the_state_of_every_lifespan(self) -> None:
        @contextlib.asynccontextmanager
        async def open_catalog(app: Kupala) -> typing.AsyncGenerator[dict[str, typing.Any]]:
            yield {"catalog": "products"}

        @contextlib.asynccontextmanager
        async def open_mailer(app: Kupala) -> typing.AsyncGenerator[dict[str, typing.Any]]:
            yield {"mailer": "smtp"}

        routes = Routes()

        @routes.get("/")
        async def index(
            catalog: typing.Annotated[str, FromState(lambda ctx, state: state.catalog)],
            mailer: typing.Annotated[str, FromState(lambda ctx, state: state.mailer)],
        ) -> Response:
            return Response(f"{catalog}/{mailer}")

        app = Kupala("tests", routes=routes, lifespans=[open_catalog, open_mailer])
        with TestClient(app) as client:
            assert client.get("/").text == "products/smtp"

    def test_the_last_lifespan_wins_a_key_collision(self) -> None:
        @contextlib.asynccontextmanager
        async def extension(app: Kupala) -> typing.AsyncGenerator[dict[str, typing.Any]]:
            yield {"db": "default"}

        @contextlib.asynccontextmanager
        async def application(app: Kupala) -> typing.AsyncGenerator[dict[str, typing.Any]]:
            yield {"db": "replaced"}

        routes = Routes()

        @routes.get("/")
        async def index(db: typing.Annotated[str, FromState(lambda ctx, state: state.db)]) -> Response:
            return Response(db)

        app = Kupala("tests", routes=routes, lifespans=[extension, application])
        with TestClient(app) as client:
            assert client.get("/").text == "replaced"

    def test_a_stateless_lifespan_contributes_nothing(self) -> None:
        @contextlib.asynccontextmanager
        async def warm_cache(app: Kupala) -> typing.AsyncGenerator[None]:
            yield None

        @contextlib.asynccontextmanager
        async def open_catalog(app: Kupala) -> typing.AsyncGenerator[dict[str, typing.Any]]:
            yield {"catalog": "products"}

        routes = Routes()

        @routes.get("/")
        async def index(request: Request) -> Response:
            return Response(",".join(sorted(request.scope["state"])))

        app = Kupala("tests", routes=routes, lifespans=[warm_cache, open_catalog])
        with TestClient(app) as client:
            assert client.get("/").text == "catalog,template_renderer"

    def test_receives_the_application_instance(self) -> None:
        # extensions read configuration off the app they are mounted on
        seen: list[Kupala] = []

        @contextlib.asynccontextmanager
        async def record(app: Kupala) -> typing.AsyncGenerator[None]:
            seen.append(app)
            yield None

        app = Kupala("tests", routes=Routes(), lifespans=[record])
        with TestClient(app):
            pass

        assert seen == [app]

    def test_starts_in_registration_order_and_shuts_down_in_reverse(self) -> None:
        # a lifespan may depend on everything registered before it, so it must tear down first
        events: list[str] = []

        @contextlib.asynccontextmanager
        async def first(app: Kupala) -> typing.AsyncGenerator[None]:
            events.append("first up")
            yield None
            events.append("first down")

        @contextlib.asynccontextmanager
        async def second(app: Kupala) -> typing.AsyncGenerator[None]:
            events.append("second up")
            yield None
            events.append("second down")

        with TestClient(Kupala("tests", routes=Routes(), lifespans=[first, second])):
            pass

        assert events == ["first up", "second up", "second down", "first down"]

    def test_unwinds_started_lifespans_when_a_later_one_fails(self) -> None:
        events: list[str] = []

        @contextlib.asynccontextmanager
        async def healthy(app: Kupala) -> typing.AsyncGenerator[None]:
            # the failure is thrown back in at the yield, so cleanup only runs from a finally block
            events.append("up")
            try:
                yield None
            finally:
                events.append("down")

        @contextlib.asynccontextmanager
        async def broken(app: Kupala) -> typing.AsyncGenerator[None]:
            raise RuntimeError("cannot connect")
            yield None  # pragma: no cover

        @contextlib.asynccontextmanager
        async def never_started(app: Kupala) -> typing.AsyncGenerator[None]:
            events.append("never")  # pragma: no cover
            yield None  # pragma: no cover

        app = Kupala("tests", routes=Routes(), lifespans=[healthy, broken, never_started])
        with pytest.raises(RuntimeError, match="cannot connect"), TestClient(app):
            pass  # pragma: no cover

        assert events == ["up", "down"]


class TestTemplateRendering:
    def test_a_route_renders_through_the_configured_engine(self) -> None:
        routes = Routes()

        @routes.get("/")
        async def index(request: Request) -> Response:
            return response(request).template("page.html", {"name": "world"})

        templates = Templates(loaders=[jinja2.DictLoader({"page.html": "hello {{ name }}"})])
        app = Kupala("tests", routes=routes, templates=templates)

        with TestClient(app) as client:
            assert client.get("/").text == "hello world"

    def test_a_lifespan_may_replace_the_renderer(self) -> None:
        replacement = Templates(loaders=[jinja2.DictLoader({"page.html": "replaced"})])

        @contextlib.asynccontextmanager
        async def override(app: Kupala) -> typing.AsyncGenerator[dict[str, typing.Any]]:
            yield {"template_renderer": replacement}

        routes = Routes()

        @routes.get("/")
        async def index(request: Request) -> Response:
            return response(request).template("page.html")

        templates = Templates(loaders=[jinja2.DictLoader({"page.html": "original"})])
        app = Kupala("tests", routes=routes, templates=templates, lifespans=[override])

        with TestClient(app) as client:
            assert client.get("/").text == "replaced"


class TestLifespanEntryPoint:
    async def test_starts_the_application_outside_a_server(self) -> None:
        @contextlib.asynccontextmanager
        async def lifespan(app: Kupala) -> typing.AsyncGenerator[dict[str, typing.Any]]:
            yield {"catalog": "loaded"}

        app = Kupala(__name__, routes=Routes(), lifespans=[lifespan])

        async with app.lifespan() as state:
            assert state == {"catalog": "loaded", "template_renderer": app.templates}

    async def test_builds_an_invocation_context_over_the_given_state(self) -> None:
        app = Kupala(__name__, routes=Routes())
        context = app.invocation_context({"catalog": "loaded"})

        assert context.state.catalog == "loaded"
        assert await context.resolve(Kupala) is app

    async def test_keeps_application_bindings_isolated(self) -> None:
        first = Kupala("first", routes=Routes(), bindings={str: constant("first")})
        second = Kupala("second", routes=Routes(), bindings={str: constant("second")})

        assert await first.invocation_context({}).resolve(str) == "first"
        assert await second.invocation_context({}).resolve(str) == "second"

    def test_request_binding_outranks_an_application_binding(self) -> None:
        routes = Routes()

        @routes.get("/")
        async def index(request: Request) -> Response:
            return Response(type(request).__name__)

        app = Kupala("tests", routes=routes, bindings={Request: constant(object())})

        with TestClient(app) as client:
            assert client.get("/").text == "Request"
