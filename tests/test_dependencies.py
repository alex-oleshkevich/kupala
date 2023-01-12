import dataclasses

import contextlib
import inspect
import pytest
import typing
from starlette.requests import Request

from kupala.dependencies import (
    Context,
    Dependency,
    DependencyResolver,
    InvalidDependency,
    InvokeContext,
    NotAnnotatedDependency,
)


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

    plan = DependencyResolver.from_callable(fn)
    assert "dep" in plan.dependencies
    dependency = plan.dependencies["dep"]
    assert dependency.factory == _dep_one_factory
    assert dependency.param_name == "dep"
    assert not dependency.optional
    assert dependency.type == DependencyOne

    assert plan.dependencies["dep2"].optional
    assert plan.dependencies["dep3"].default_value is None
    assert isinstance(plan.dependencies["dep4"].default_value, DependencyOne)


def test_requires_annotated_parameters() -> None:
    def fn(
        dep: DependencyOne,
    ) -> DependencyOne:
        return dep

    with pytest.raises(NotAnnotatedDependency):
        DependencyResolver.from_callable(fn)


@pytest.mark.asyncio
async def test_execute_injection_plan() -> None:
    def fn(dep: DepOne) -> str:
        return dep.value

    conn = Request({"type": "http"})
    plan = DependencyResolver.from_callable(fn)
    result = await plan.execute(conn)
    assert result == "sync"


@pytest.mark.asyncio
async def test_execute_injection_plan_with_async_peer_dependency() -> None:
    def fn(dep: AsyncDepOne) -> str:
        return dep.value

    conn = Request({"type": "http"})
    plan = DependencyResolver.from_callable(fn)
    result = await plan.execute(conn)
    assert result == "async"


@pytest.mark.asyncio
async def test_execute_injection_plan_with_async_dependency() -> None:
    async def fn(dep: AsyncDepOne) -> str:
        return dep.value

    conn = Request({"type": "http"})
    plan = DependencyResolver.from_callable(fn)
    result = await plan.execute(conn)
    assert result == "async"


@pytest.mark.asyncio
async def test_non_optional_dependency_disallows_none_value() -> None:
    Dep = typing.Annotated[DependencyOne, lambda context: None]

    def fn(dep: Dep) -> str:
        return str(dep)

    with pytest.raises(InvalidDependency, match="returned None"):
        conn = Request({"type": "http"})
        plan = DependencyResolver.from_callable(fn)
        await plan.execute(conn)


@pytest.mark.asyncio
async def test_optional_dependency_allows_none_value() -> None:
    Dep = typing.Annotated[DependencyOne, lambda context: None]

    def fn(dep: Dep | None) -> str:
        return str(dep)

    conn = Request({"type": "http"})
    plan = DependencyResolver.from_callable(fn)
    result = await plan.execute(conn)
    assert result == "None"


@pytest.mark.asyncio
async def test_injects_context_into_factory() -> None:
    def factory(context: Context) -> str:
        return context.__class__.__name__

    Dep = typing.Annotated[str, factory]

    def fn(dep: Dep) -> str:
        return dep

    conn = Request({"type": "http"})
    plan = DependencyResolver.from_callable(fn)
    result = await plan.execute(conn)
    assert result == "Context"


@pytest.mark.asyncio
async def test_not_injects_context_into_factory() -> None:
    def factory() -> str:
        return "none"

    Dep = typing.Annotated[str, factory]

    def fn(dep: Dep) -> str:
        return dep

    conn = Request({"type": "http"})
    plan = DependencyResolver.from_callable(fn)
    result = await plan.execute(conn)
    assert result == "none"


@pytest.mark.asyncio
async def test_resolves_nested_dependencies() -> None:
    def parent_factory(context: Context) -> str:
        return "parent"

    Parent = typing.Annotated[str, parent_factory]

    def child_factory(context: Context, parent: Parent) -> str:
        return parent + "child"

    Child = typing.Annotated[str, child_factory]

    def fn(dep: Child) -> str:
        return dep

    conn = Request({"type": "http"})
    plan = DependencyResolver.from_callable(fn)
    result = await plan.execute(conn)
    assert result == "parentchild"


@pytest.mark.asyncio
async def test_sync_context_manager_dependencies() -> None:
    @contextlib.contextmanager
    def factory(context: Context) -> typing.Generator[str, None, None]:
        yield "dep"

    Dep = typing.Annotated[str, factory]

    def fn(dep: Dep) -> str:
        return dep

    conn = Request({"type": "http"})
    plan = DependencyResolver.from_callable(fn)
    result = await plan.execute(conn)
    assert result == "dep"


@pytest.mark.asyncio
async def test_sync_context_manager_dependencies_recursive() -> None:
    @contextlib.contextmanager
    def base_factory(context: Context) -> typing.Generator[str, None, None]:
        yield "base"

    Base = typing.Annotated[str, base_factory]

    @contextlib.contextmanager
    def factory(context: Context, base: Base) -> typing.Generator[str, None, None]:
        yield base + "dep"

    Dep = typing.Annotated[str, factory]

    def fn(dep: Dep) -> str:
        return dep

    conn = Request({"type": "http"})
    plan = DependencyResolver.from_callable(fn)
    result = await plan.execute(conn)
    assert result == "basedep"


@pytest.mark.asyncio
async def test_async_context_manager_dependencies() -> None:
    @contextlib.asynccontextmanager
    async def factory(context: Context) -> typing.AsyncGenerator[str, None]:
        yield "dep"

    Dep = typing.Annotated[str, factory]

    def fn(dep: Dep) -> str:
        return dep

    conn = Request({"type": "http"})
    plan = DependencyResolver.from_callable(fn)
    result = await plan.execute(conn)
    assert result == "dep"


@pytest.mark.asyncio
async def test_async_context_manager_dependencies_recursive() -> None:
    @contextlib.asynccontextmanager
    async def base_factory(context: Context) -> typing.AsyncGenerator[str, None]:
        yield "base"

    Base = typing.Annotated[str, base_factory]

    @contextlib.asynccontextmanager
    async def factory(context: Context, base: Base) -> typing.AsyncGenerator[str, None]:
        yield base + "dep"

    Dep = typing.Annotated[str, factory]

    def fn(dep: Dep) -> str:
        return dep

    conn = Request({"type": "http"})
    plan = DependencyResolver.from_callable(fn)
    result = await plan.execute(conn)
    assert result == "basedep"


@pytest.mark.asyncio
async def test_dependency_resolve_not_caches() -> None:
    parameter = inspect.Parameter(
        "name",
        kind=inspect.Parameter.KEYWORD_ONLY,
        annotation=typing.Annotated[int, lambda context: id(context.request)],
    )
    dependency = Dependency.from_parameter(parameter)
    with contextlib.ExitStack() as exit_stack:
        async with contextlib.AsyncExitStack() as aexit_stack:
            call_1 = await dependency.resolve(
                InvokeContext(
                    extras={"request": Request({"type": "http"})}, exit_stack=exit_stack, aexit_stack=aexit_stack
                )
            )
            call_2 = await dependency.resolve(
                InvokeContext(
                    extras={"request": Request({"type": "http"})}, exit_stack=exit_stack, aexit_stack=aexit_stack
                )
            )
            assert call_1 != call_2


@pytest.mark.asyncio
async def test_dependency_overrides() -> None:
    def factory() -> str:
        return "dep"

    def override_factory() -> str:
        return "override"

    Dep = typing.Annotated[str, factory]

    def fn(dep: Dep) -> str:
        return dep

    conn = Request({"type": "http"})
    plan = DependencyResolver.from_callable(
        fn,
        overrides={
            "dep": Dependency.from_parameter(
                inspect.Parameter(
                    name="dep", kind=inspect.Parameter.KEYWORD_ONLY, annotation=typing.Annotated[str, override_factory]
                )
            )
        },
    )
    result = await plan.execute(conn)
    assert result == "override"
