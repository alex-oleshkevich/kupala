import contextlib
import typing

import pytest
from starlette.exceptions import HTTPException
from starlette.testclient import TestClient

from kupala.applications import Kupala
from kupala.dependencies import INVOCATION_CONTEXT_KEY, Factory, FromState, InvocationContext, Value
from kupala.middleware import CallNext, WebSocketCallNext
from kupala.requests import Request
from kupala.responses import Response, StreamingResponse
from kupala.routing import Routes
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
        class StubRequest: ...

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
        class App(Kupala):
            @contextlib.asynccontextmanager
            async def lifespan(self, app: typing.Self) -> typing.AsyncGenerator[dict[str, typing.Any]]:
                yield {"catalog": "loaded once"}

        routes = Routes()

        @routes.get("/")
        async def index(catalog: typing.Annotated[str, FromState(lambda ctx, state: state.catalog)]) -> Response:
            return Response(catalog)

        with TestClient(App("tests", routes=routes)) as client:
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
