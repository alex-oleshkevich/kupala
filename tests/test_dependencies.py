import dataclasses

import contextlib
import pytest
import typing
from starlette.requests import HTTPConnection

from kupala.dependencies import Context, InjectionPlan, InvalidInjection


@dataclasses.dataclass
class DependencyOne:
    value: str


def _dep_one_factory() -> DependencyOne:
    return DependencyOne(value="sync")


DepOne = typing.Annotated[DependencyOne, _dep_one_factory]


async def _async_dep_one_factory() -> DependencyOne:
    return DependencyOne(value="async")


AsyncDepOne = typing.Annotated[DependencyOne, _async_dep_one_factory]


def test_generates_injection_plan() -> None:
    def fn(
        dep: DepOne,
        async_dep: AsyncDepOne,
        dep2: DepOne | None,
        dep3: DepOne | None = None,
        dep4: DepOne = DependencyOne(""),
    ) -> DependencyOne:
        return dep

    plan = InjectionPlan.from_callable(fn)
    assert "dep" in plan.dependencies
    dependency = plan.dependencies["dep"]
    assert dependency.factory == _dep_one_factory
    assert dependency.param_name == "dep"
    assert not dependency.optional
    assert dependency.type == DependencyOne

    assert plan.dependencies["dep2"].optional
    assert plan.dependencies["dep3"].default_value is None
    assert isinstance(plan.dependencies["dep4"].default_value, DependencyOne)
    assert plan.dependencies["async_dep"].is_async


@pytest.mark.asyncio
async def test_execute_injection_plan() -> None:
    def fn(dep: DepOne) -> str:
        return dep.value

    conn = HTTPConnection({"type": "http"})
    plan = InjectionPlan.from_callable(fn)
    result = await plan.execute(conn)
    assert result == "sync"


@pytest.mark.asyncio
async def test_execute_injection_plan_with_async_peer_dependency() -> None:
    def fn(dep: AsyncDepOne) -> str:
        return dep.value

    conn = HTTPConnection({"type": "http"})
    plan = InjectionPlan.from_callable(fn)
    result = await plan.execute(conn)
    assert result == "async"


@pytest.mark.asyncio
async def test_execute_injection_plan_with_async_dependency() -> None:
    async def fn(dep: AsyncDepOne) -> str:
        return dep.value

    conn = HTTPConnection({"type": "http"})
    plan = InjectionPlan.from_callable(fn)
    result = await plan.execute(conn)
    assert result == "async"


@pytest.mark.asyncio
async def test_non_optional_dependency_disallows_none_value() -> None:
    Dep = typing.Annotated[DependencyOne, lambda: None]

    def fn(dep: Dep) -> str:
        return str(dep)

    with pytest.raises(InvalidInjection, match="returned None"):
        conn = HTTPConnection({"type": "http"})
        plan = InjectionPlan.from_callable(fn)
        await plan.execute(conn)


@pytest.mark.asyncio
async def test_optional_dependency_allows_none_value() -> None:
    Dep = typing.Annotated[DependencyOne, lambda: None]

    def fn(dep: Dep | None) -> str:
        return str(dep)

    conn = HTTPConnection({"type": "http"})
    plan = InjectionPlan.from_callable(fn)
    result = await plan.execute(conn)
    assert result == "None"


@pytest.mark.asyncio
async def test_injects_context_into_factory() -> None:
    def factory(context: Context) -> str:
        return context.__class__.__name__

    Dep = typing.Annotated[str, factory]

    def fn(dep: Dep) -> str:
        return dep

    conn = HTTPConnection({"type": "http"})
    plan = InjectionPlan.from_callable(fn)
    result = await plan.execute(conn)
    assert result == "_Context"


@pytest.mark.asyncio
async def test_resolves_nested_dependencies() -> None:
    def parent_factory() -> str:
        return "parent"

    Parent = typing.Annotated[str, parent_factory]

    def child_factory(parent: Parent) -> str:
        return parent + "child"

    Child = typing.Annotated[str, child_factory]

    def fn(dep: Child) -> str:
        return dep

    conn = HTTPConnection({"type": "http"})
    plan = InjectionPlan.from_callable(fn)
    result = await plan.execute(conn)
    assert result == "parentchild"


@pytest.mark.asyncio
async def test_sync_context_manager_dependencies() -> None:
    @contextlib.contextmanager
    def factory() -> typing.Generator[str, None, None]:
        yield "dep"

    Dep = typing.Annotated[str, factory]

    def fn(dep: Dep) -> str:
        return dep

    conn = HTTPConnection({"type": "http"})
    plan = InjectionPlan.from_callable(fn)
    result = await plan.execute(conn)
    assert result == "dep"


@pytest.mark.asyncio
async def test_sync_context_manager_dependencies_recursive() -> None:
    @contextlib.contextmanager
    def base_factory() -> typing.Generator[str, None, None]:
        yield "base"

    Base = typing.Annotated[str, base_factory]

    @contextlib.contextmanager
    def factory(base: Base) -> typing.Generator[str, None, None]:
        yield base + "dep"

    Dep = typing.Annotated[str, factory]

    def fn(dep: Dep) -> str:
        return dep

    conn = HTTPConnection({"type": "http"})
    plan = InjectionPlan.from_callable(fn)
    result = await plan.execute(conn)
    assert result == "basedep"


@pytest.mark.asyncio
async def test_async_context_manager_dependencies() -> None:
    @contextlib.asynccontextmanager
    async def factory() -> typing.AsyncGenerator[str, None]:
        yield "dep"

    Dep = typing.Annotated[str, factory]

    def fn(dep: Dep) -> str:
        return dep

    conn = HTTPConnection({"type": "http"})
    plan = InjectionPlan.from_callable(fn)
    result = await plan.execute(conn)
    assert result == "dep"


@pytest.mark.asyncio
async def test_async_context_manager_dependencies_recursive() -> None:
    @contextlib.asynccontextmanager
    async def base_factory() -> typing.AsyncGenerator[str, None]:
        yield "base"

    Base = typing.Annotated[str, base_factory]

    @contextlib.asynccontextmanager
    async def factory(base: Base) -> typing.AsyncGenerator[str, None]:
        yield base + "dep"

    Dep = typing.Annotated[str, factory]

    def fn(dep: Dep) -> str:
        return dep

    conn = HTTPConnection({"type": "http"})
    plan = InjectionPlan.from_callable(fn)
    result = await plan.execute(conn)
    assert result == "basedep"
