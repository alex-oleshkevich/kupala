from kupala.dependencies import DependencyResolver


class TestDependencyResolver:
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
