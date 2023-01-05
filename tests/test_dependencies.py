import dataclasses

import pytest
import typing
from starlette.requests import HTTPConnection

from kupala.dependencies import Context, InvalidInjection, resolve_dependencies


@dataclasses.dataclass
class DependencyOne:
    value: str


def _dep_one_factory(context: Context) -> DependencyOne:
    return DependencyOne(value="sync")


DepOne = typing.Annotated[DependencyOne, _dep_one_factory]


async def _async_dep_one_factory(context: Context) -> DependencyOne:
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

    plan = resolve_dependencies(fn)
    assert "dep" in plan.dependencies
    dependency = plan.dependencies["dep"]
    assert dependency.factory == _dep_one_factory
    assert dependency.param_name == "dep"
    assert not dependency.optional
    assert dependency.base_type == DependencyOne

    assert plan.dependencies["dep2"].optional
    assert plan.dependencies["dep3"].default_value is None
    assert isinstance(plan.dependencies["dep4"].default_value, DependencyOne)
    assert plan.dependencies["async_dep"].is_async


@pytest.mark.asyncio
async def test_execute_injection_plan() -> None:
    def fn(dep: DepOne) -> str:
        return dep.value

    conn = HTTPConnection({"type": "http"})
    plan = resolve_dependencies(fn)
    result = await plan.execute(conn)
    assert result == "sync"


@pytest.mark.asyncio
async def test_execute_injection_plan_with_async_dependency() -> None:
    def fn(dep: AsyncDepOne) -> str:
        return dep.value

    conn = HTTPConnection({"type": "http"})
    plan = resolve_dependencies(fn)
    result = await plan.execute(conn)
    assert result == "async"


@pytest.mark.asyncio
async def test_non_optional_dependency_disallows_none_value() -> None:
    Dep = typing.Annotated[DependencyOne, lambda context: None]

    def fn(dep: Dep) -> str:
        return str(dep)

    with pytest.raises(InvalidInjection, match="returned None"):
        conn = HTTPConnection({"type": "http"})
        plan = resolve_dependencies(fn)
        await plan.execute(conn)


@pytest.mark.asyncio
async def test_optional_dependency_allows_none_value() -> None:
    Dep = typing.Annotated[DependencyOne, lambda context: None]

    def fn(dep: Dep | None) -> str:
        return str(dep)

    conn = HTTPConnection({"type": "http"})
    plan = resolve_dependencies(fn)
    result = await plan.execute(conn)
    assert result == "None"
