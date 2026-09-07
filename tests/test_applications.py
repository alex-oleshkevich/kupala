import typing

from starlette.exceptions import HTTPException
from starlette.testclient import TestClient

from kupala.applications import Kupala
from kupala.dependencies import Factory
from kupala.responses import Response, StreamingResponse
from kupala.routing import Routes


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
