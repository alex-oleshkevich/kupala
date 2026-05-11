import typing

from kupala.middleware import build_asgi_middleware_stack, with_options
from kupala.types import ASGIApp


class FakeMW:
    def __init__(self, app: ASGIApp, name: str = "") -> None:
        self.app = app
        self.name = name

    async def __call__(self, scope: typing.Any, receive: typing.Any, send: typing.Any) -> None:
        await self.app(scope, receive, send)


class PositionalMW:
    def __init__(self, app: ASGIApp, value: int) -> None:
        self.app = app
        self.value = value

    async def __call__(self, scope: typing.Any, receive: typing.Any, send: typing.Any) -> None:
        await self.app(scope, receive, send)


async def _router_fn(scope: typing.Any, receive: typing.Any, send: typing.Any) -> None:
    pass


async def _other_router_fn(scope: typing.Any, receive: typing.Any, send: typing.Any) -> None:
    pass


_router: ASGIApp = typing.cast(ASGIApp, _router_fn)
_other_router: ASGIApp = typing.cast(ASGIApp, _other_router_fn)


class TestWithOptions:
    def test_returns_callable(self) -> None:
        factory = with_options(FakeMW, name="x")
        assert callable(factory)

    def test_binds_kwargs(self) -> None:
        factory = with_options(FakeMW, name="alpha")
        mw = factory(_router)
        assert isinstance(mw, FakeMW)
        assert mw.name == "alpha"
        assert mw.app is _router

    def test_binds_positional_args(self) -> None:
        factory = with_options(PositionalMW, 42)
        mw = factory(_router)
        assert isinstance(mw, PositionalMW)
        assert mw.value == 42
        assert mw.app is _router

    def test_calls_with_inner_app(self) -> None:
        factory = with_options(FakeMW, name="x")
        mw1 = factory(_router)
        mw2 = factory(_other_router)
        assert isinstance(mw1, FakeMW)
        assert isinstance(mw2, FakeMW)
        assert mw1.app is _router
        assert mw2.app is _other_router


class TestBuildMiddlewareStack:
    def test_empty_returns_router(self) -> None:
        result = build_asgi_middleware_stack([], _router)
        assert result is _router

    def test_single_middleware(self) -> None:
        result = build_asgi_middleware_stack([with_options(FakeMW, name="a")], _router)
        assert isinstance(result, FakeMW)
        assert result.name == "a"
        assert result.app is _router

    def test_first_is_outermost(self) -> None:
        result = build_asgi_middleware_stack(
            [with_options(FakeMW, name="A"), with_options(FakeMW, name="B")],
            _router,
        )
        assert isinstance(result, FakeMW)
        assert result.name == "A"
        assert isinstance(result.app, FakeMW)
        assert result.app.name == "B"
        assert result.app.app is _router

    def test_router_at_innermost(self) -> None:
        stack = build_asgi_middleware_stack(
            [
                with_options(FakeMW, name="a"),
                with_options(FakeMW, name="b"),
                with_options(FakeMW, name="c"),
            ],
            _router,
        )
        assert isinstance(stack, FakeMW)
        assert isinstance(stack.app, FakeMW)
        assert isinstance(stack.app.app, FakeMW)
        assert stack.app.app.app is _router
