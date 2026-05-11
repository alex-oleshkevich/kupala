import asyncio
import contextlib
import typing

import pytest

from kupala.app import Kupala
from kupala.lifespan import Lifespan, lifespan_handler
from kupala.types import Receive, ReceiveMessage, Scope, Send, SendMessage

APP: Kupala = typing.cast(Kupala, object())


def make_lifespan_io(
    scope: dict[str, typing.Any] | None = None,
) -> tuple[Scope, Receive, Send, list[SendMessage]]:
    if scope is None:
        scope = {
            "type": "lifespan",
            "asgi": {"version": "3.0", "spec_version": "2.0"},
            "state": {},
        }
    out: list[SendMessage] = []
    in_iter = iter([{"type": "lifespan.startup"}, {"type": "lifespan.shutdown"}])

    async def receive() -> ReceiveMessage:
        return typing.cast(ReceiveMessage, next(in_iter))

    async def send(message: SendMessage) -> None:
        out.append(message)

    return typing.cast(Scope, scope), typing.cast(Receive, receive), typing.cast(Send, send), out


class TestProtocol:
    async def test_empty_lifespan_runs_full_cycle(self) -> None:
        scope, receive, send, out = make_lifespan_io()
        handler = lifespan_handler(APP, [])
        await handler(scope, receive, send)
        assert [m["type"] for m in out] == [
            "lifespan.startup.complete",
            "lifespan.shutdown.complete",
        ]

    async def test_missing_state_key_raises(self) -> None:
        """Spec 2.0 requires servers to put "state" in the lifespan scope; fail loud if they don't."""

        @contextlib.asynccontextmanager
        async def lf(_: Kupala) -> typing.AsyncIterator[typing.Mapping[str, typing.Any]]:
            yield {"x": 1}

        scope, receive, send, _ = make_lifespan_io(
            scope={"type": "lifespan", "asgi": {"version": "3.0", "spec_version": "2.0"}},
        )
        handler = lifespan_handler(APP, [lf])

        with pytest.raises(KeyError):
            await handler(scope, receive, send)


class TestInvocation:
    async def test_each_lifespan_called_once_with_app(self) -> None:
        received: list[tuple[str, object]] = []

        def make_lf(name: str) -> Lifespan:
            @contextlib.asynccontextmanager
            async def lf(a: Kupala) -> typing.AsyncIterator[None]:
                received.append((name, a))
                yield None

            return lf

        scope, receive, send, _ = make_lifespan_io()
        handler = lifespan_handler(APP, [make_lf("a"), make_lf("b"), make_lf("c")])
        await handler(scope, receive, send)

        assert received == [("a", APP), ("b", APP), ("c", APP)]

    async def test_startup_then_shutdown_in_lifo_order(self) -> None:
        events: list[str] = []

        def make_lf(name: str) -> Lifespan:
            @contextlib.asynccontextmanager
            async def lf(_: Kupala) -> typing.AsyncIterator[None]:
                events.append(f"enter:{name}")
                try:
                    yield None
                finally:
                    events.append(f"exit:{name}")

            return lf

        scope, receive, send, out = make_lifespan_io()

        async def tracking_send(message: SendMessage) -> None:
            events.append(f"send:{message['type']}")
            out.append(message)

        handler = lifespan_handler(APP, [make_lf("a"), make_lf("b"), make_lf("c")])
        await handler(scope, receive, tracking_send)

        assert events == [
            "enter:a",
            "enter:b",
            "enter:c",
            "send:lifespan.startup.complete",
            "exit:c",
            "exit:b",
            "exit:a",
            "send:lifespan.shutdown.complete",
        ]


class TestStatePropagation:
    async def test_yielded_mapping_merged(self) -> None:
        sentinel = object()

        @contextlib.asynccontextmanager
        async def lf(_: Kupala) -> typing.AsyncIterator[typing.Mapping[str, typing.Any]]:
            yield {"db": sentinel}

        scope, receive, send, _ = make_lifespan_io()
        handler = lifespan_handler(APP, [lf])
        await handler(scope, receive, send)

        assert scope["state"] == {"db": sentinel}

    async def test_later_lifespan_overwrites_earlier_keys(self) -> None:
        @contextlib.asynccontextmanager
        async def first(app: Kupala) -> typing.AsyncIterator[typing.Mapping[str, typing.Any]]:
            yield {"k": "first"}

        @contextlib.asynccontextmanager
        async def second(app: Kupala) -> typing.AsyncIterator[typing.Mapping[str, typing.Any]]:
            yield {"k": "second"}

        scope, receive, send, _ = make_lifespan_io()
        handler = lifespan_handler(APP, [first, second])
        await handler(scope, receive, send)

        assert scope["state"] == {"k": "second"}

    async def test_yielding_none_leaves_state_empty(self) -> None:
        @contextlib.asynccontextmanager
        async def lf(app: Kupala) -> typing.AsyncIterator[None]:
            yield None

        scope, receive, send, _ = make_lifespan_io()
        handler = lifespan_handler(APP, [lf])
        await handler(scope, receive, send)

        assert scope["state"] == {}


class TestStartupFailure:
    async def test_exception_sends_failed_and_reraises(self) -> None:
        @contextlib.asynccontextmanager
        async def boom(_: Kupala) -> typing.AsyncIterator[None]:
            raise RuntimeError("startup boom")
            yield None

        scope, receive, send, out = make_lifespan_io()
        handler = lifespan_handler(APP, [boom])

        with pytest.raises(RuntimeError, match="startup boom"):
            await handler(scope, receive, send)

        assert len(out) == 1
        assert out[0]["type"] == "lifespan.startup.failed"
        assert "RuntimeError" in out[0]["message"]
        assert "startup boom" in out[0]["message"]

    async def test_partial_startup_unwinds_completed_lifespans(self) -> None:
        events: list[str] = []

        @contextlib.asynccontextmanager
        async def ok_a(_: Kupala) -> typing.AsyncIterator[None]:
            events.append("enter:a")
            try:
                yield None
            finally:
                events.append("exit:a")

        @contextlib.asynccontextmanager
        async def ok_b(_: Kupala) -> typing.AsyncIterator[None]:
            events.append("enter:b")
            try:
                yield None
            finally:
                events.append("exit:b")

        @contextlib.asynccontextmanager
        async def boom(_: Kupala) -> typing.AsyncIterator[None]:
            events.append("enter:c")
            raise RuntimeError("c failed")
            yield None

        scope, receive, send, _ = make_lifespan_io()
        handler = lifespan_handler(APP, [ok_a, ok_b, boom])

        with pytest.raises(RuntimeError, match="c failed"):
            await handler(scope, receive, send)

        assert events == ["enter:a", "enter:b", "enter:c", "exit:b", "exit:a"]

    async def test_no_shutdown_complete_on_startup_failure(self) -> None:
        @contextlib.asynccontextmanager
        async def boom(_: Kupala) -> typing.AsyncIterator[None]:
            raise RuntimeError("nope")
            yield None

        scope, receive, send, out = make_lifespan_io()
        handler = lifespan_handler(APP, [boom])

        with pytest.raises(RuntimeError):
            await handler(scope, receive, send)

        assert [m["type"] for m in out] == ["lifespan.startup.failed"]


class TestShutdownFailure:
    async def test_exception_sends_failed_and_reraises(self) -> None:
        @contextlib.asynccontextmanager
        async def lf(_: Kupala) -> typing.AsyncIterator[None]:
            yield None
            raise RuntimeError("shutdown boom")

        scope, receive, send, out = make_lifespan_io()
        handler = lifespan_handler(APP, [lf])

        with pytest.raises(RuntimeError, match="shutdown boom"):
            await handler(scope, receive, send)

        assert len(out) == 2
        assert out[0]["type"] == "lifespan.startup.complete"
        assert out[1]["type"] == "lifespan.shutdown.failed"
        assert "shutdown boom" in out[1]["message"]


class TestCancellation:
    async def test_cancellederror_propagates_unreported(self) -> None:
        """Handler catches Exception (not BaseException) so cancellation isn't misreported as a lifespan failure."""

        @contextlib.asynccontextmanager
        async def cancels(_: Kupala) -> typing.AsyncIterator[None]:
            raise asyncio.CancelledError()
            yield None

        scope, receive, send, out = make_lifespan_io()
        handler = lifespan_handler(APP, [cancels])

        with pytest.raises(asyncio.CancelledError):
            await handler(scope, receive, send)

        assert out == []
