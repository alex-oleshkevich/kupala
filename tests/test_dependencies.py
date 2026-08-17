import pytest

from kupala.dependencies import DependencyResolver


class TestDependencyResolver:
    async def test_invoke_rejects_positional_arguments(self) -> None:
        async def endpoint(request: str = "resolved") -> str:
            return request  # pragma: no cover

        with pytest.raises(TypeError, match="Positional arguments are not supported"):
            await DependencyResolver().invoke(endpoint, "positional")

    async def test_invoke_forwards_keyword_overrides(self) -> None:
        async def endpoint(request: str = "resolved") -> str:
            return request

        assert await DependencyResolver().invoke(endpoint) == "resolved"
        assert await DependencyResolver().invoke(endpoint, request="override") == "override"

    def test_bind_forwards_keyword_overrides(self) -> None:
        def endpoint(request: str = "resolved") -> str:
            return request

        bound = DependencyResolver().bind(endpoint)

        assert bound() == "resolved"
        assert bound(request="override") == "override"

    async def test_bind_preserves_async_callables(self) -> None:
        async def endpoint(request: str = "resolved") -> str:
            return request

        async def exercise() -> None:
            bound = DependencyResolver().bind(endpoint)

            assert await bound() == "resolved"
            assert await bound(request="override") == "override"

        await exercise()
