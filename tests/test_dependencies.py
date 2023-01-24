import dataclasses

import contextlib
import functools
import inspect
import pytest
import typing
from starlette.applications import Starlette
from starlette.requests import Request

from kupala.dependencies import (
    Argument,
    Dependency,
    DependencyResolver,
    InvalidDependency,
    InvokeContext,
    NotAnnotatedDependency,
)


@dataclasses.dataclass
class DependencyOne:
    value: str


def _dep_one_factory(context: Argument) -> DependencyOne:
    return DependencyOne(value="sync")


DepOne = typing.Annotated[DependencyOne, _dep_one_factory]


async def _async_dep_one_factory(context: Argument) -> DependencyOne:
    return DependencyOne(value="async")


AsyncDepOne = typing.Annotated[DependencyOne, _async_dep_one_factory]


def test_generates_injection_plan() -> None:
    def fn(
        dep: DepOne,
        async_dep: AsyncDepOne,
        dep2: DepOne | None,
        dep3: DepOne | None = None,
        dep4: DepOne = DependencyOne(""),
    ) -> None:  # pragma: nocover
        ...

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
    ) -> None:  # pragma: nocover
        ...

    with pytest.raises(NotAnnotatedDependency):
        DependencyResolver.from_callable(fn)


@pytest.mark.asyncio
async def test_execute_injection_plan() -> None:
    def fn(dep: DepOne) -> str:
        return dep.value

    app = Starlette()
    conn = Request({"type": "http"})
    plan = DependencyResolver.from_callable(fn)
    result = await plan.execute(InvokeContext(request=conn, app=app))
    assert result == "sync"


@pytest.mark.asyncio
async def test_execute_injection_plan_with_async_peer_dependency() -> None:
    def fn(dep: AsyncDepOne) -> str:
        return dep.value

    app = Starlette()
    conn = Request({"type": "http"})
    plan = DependencyResolver.from_callable(fn)
    result = await plan.execute(InvokeContext(request=conn, app=app))
    assert result == "async"


@pytest.mark.asyncio
async def test_execute_injection_plan_with_async_dependency() -> None:
    async def fn(dep: AsyncDepOne) -> str:
        return dep.value

    app = Starlette()
    conn = Request({"type": "http"})
    plan = DependencyResolver.from_callable(fn)
    result = await plan.execute(InvokeContext(request=conn, app=app))
    assert result == "async"


@pytest.mark.asyncio
async def test_non_optional_dependency_disallows_none_value() -> None:
    Dep = typing.Annotated[DependencyOne, lambda context: None]

    def fn(dep: Dep) -> None:  # pragma: nocover
        ...

    with pytest.raises(InvalidDependency, match="returned None"):
        app = Starlette()
        conn = Request({"type": "http"})
        plan = DependencyResolver.from_callable(fn)
        await plan.execute(InvokeContext(request=conn, app=app))


@pytest.mark.asyncio
async def test_optional_dependency_allows_none_value() -> None:
    Dep = typing.Annotated[DependencyOne, lambda context: None]

    def fn(dep: Dep | None) -> str:
        return str(dep)

    app = Starlette()
    conn = Request({"type": "http"})
    plan = DependencyResolver.from_callable(fn)
    result = await plan.execute(InvokeContext(request=conn, app=app))
    assert result == "None"


@pytest.mark.asyncio
async def test_injects_context_into_factory() -> None:
    def factory(argument: Argument) -> str:
        return argument.__class__.__name__

    Dep = typing.Annotated[str, factory]

    def fn(dep: Dep) -> str:
        return dep

    app = Starlette()
    conn = Request({"type": "http"})
    plan = DependencyResolver.from_callable(fn)
    result = await plan.execute(InvokeContext(request=conn, app=app))
    assert result == "Argument"


@pytest.mark.asyncio
async def test_not_injects_context_into_factory() -> None:
    def factory() -> str:
        return "none"

    Dep = typing.Annotated[str, factory]

    def fn(dep: Dep) -> str:
        return dep

    app = Starlette()
    conn = Request({"type": "http"})
    plan = DependencyResolver.from_callable(fn)
    result = await plan.execute(InvokeContext(request=conn, app=app))
    assert result == "none"


@pytest.mark.asyncio
async def test_resolves_nested_dependencies() -> None:
    def parent_factory(context: Argument) -> str:
        return "parent"

    Parent = typing.Annotated[str, parent_factory]

    def child_factory(context: Argument, parent: Parent) -> str:
        return parent + "child"

    Child = typing.Annotated[str, child_factory]

    def fn(dep: Child) -> str:
        return dep

    app = Starlette()
    conn = Request({"type": "http"})
    plan = DependencyResolver.from_callable(fn)
    result = await plan.execute(InvokeContext(request=conn, app=app))
    assert result == "parentchild"


@pytest.mark.asyncio
async def test_sync_context_manager_dependencies() -> None:
    @contextlib.contextmanager
    def factory(context: Argument) -> typing.Generator[str, None, None]:
        yield "dep"

    Dep = typing.Annotated[str, factory]

    def fn(dep: Dep) -> str:
        return dep

    app = Starlette()
    conn = Request({"type": "http"})
    plan = DependencyResolver.from_callable(fn)
    result = await plan.execute(InvokeContext(request=conn, app=app))
    assert result == "dep"


@pytest.mark.asyncio
async def test_sync_context_manager_dependencies_recursive() -> None:
    @contextlib.contextmanager
    def base_factory(context: Argument) -> typing.Generator[str, None, None]:
        yield "base"

    Base = typing.Annotated[str, base_factory]

    @contextlib.contextmanager
    def factory(context: Argument, base: Base) -> typing.Generator[str, None, None]:
        yield base + "dep"

    Dep = typing.Annotated[str, factory]

    def fn(dep: Dep) -> str:
        return dep

    app = Starlette()
    conn = Request({"type": "http"})
    plan = DependencyResolver.from_callable(fn)
    result = await plan.execute(InvokeContext(request=conn, app=app))
    assert result == "basedep"


@pytest.mark.asyncio
async def test_async_context_manager_dependencies() -> None:
    @contextlib.asynccontextmanager
    async def factory(context: Argument) -> typing.AsyncGenerator[str, None]:
        yield "dep"

    Dep = typing.Annotated[str, factory]

    def fn(dep: Dep) -> str:
        return dep

    app = Starlette()
    conn = Request({"type": "http"})
    plan = DependencyResolver.from_callable(fn)
    result = await plan.execute(InvokeContext(request=conn, app=app))
    assert result == "dep"


@pytest.mark.asyncio
async def test_async_context_manager_dependencies_recursive() -> None:
    @contextlib.asynccontextmanager
    async def base_factory(context: Argument) -> typing.AsyncGenerator[str, None]:
        yield "base"

    Base = typing.Annotated[str, base_factory]

    @contextlib.asynccontextmanager
    async def factory(context: Argument, base: Base) -> typing.AsyncGenerator[str, None]:
        yield base + "dep"

    Dep = typing.Annotated[str, factory]

    def fn(dep: Dep) -> str:
        return dep

    app = Starlette()
    conn = Request({"type": "http"})
    plan = DependencyResolver.from_callable(fn)
    result = await plan.execute(InvokeContext(request=conn, app=app))
    assert result == "basedep"


@pytest.mark.asyncio
async def test_dependency_resolve_not_caches() -> None:
    parameter = inspect.Parameter(
        "name",
        kind=inspect.Parameter.KEYWORD_ONLY,
        annotation=typing.Annotated[int, lambda request: id(request)],
    )
    app = Starlette()
    dependency = Dependency.from_parameter(parameter)
    call_1 = await dependency.resolve(InvokeContext(request=Request({"type": "http"}), app=app))
    call_2 = await dependency.resolve(InvokeContext(request=Request({"type": "http"}), app=app))
    assert call_1 != call_2


@pytest.mark.asyncio
async def test_dependency_overrides() -> None:
    def factory() -> str:  # pragma: nocover
        return "dep"

    def override_factory() -> str:
        return "override"

    Dep = typing.Annotated[str, factory]

    def fn(dep: Dep) -> str:
        return dep

    app = Starlette()
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
    result = await plan.execute(InvokeContext(request=conn, app=app))
    assert result == "override"


@pytest.mark.asyncio
async def test_injects_request_by_class() -> None:
    def fn(request: Request) -> str:
        return request.__class__.__name__

    app = Starlette()
    conn = Request({"type": "http"})
    plan = DependencyResolver.from_callable(fn)
    result = await plan.execute(InvokeContext(request=conn, app=app))
    assert result == "Request"


@pytest.mark.asyncio
async def test_injects_request_by_name() -> None:
    app = Starlette()
    conn = Request({"type": "http"})
    plan = DependencyResolver.from_callable(lambda request: request.__class__.__name__)
    result = await plan.execute(InvokeContext(request=conn, app=app))
    assert result == "Request"


@pytest.mark.asyncio
async def test_injects_request_subclass() -> None:
    class MyRequest(Request):
        ...

    def fn(request: MyRequest) -> str:
        return request.__class__.__name__

    app = Starlette()
    conn = Request({"type": "http"})
    plan = DependencyResolver.from_callable(fn)
    result = await plan.execute(InvokeContext(request=conn, app=app))
    assert result == "MyRequest"


async def test_injects_optional_dependency_with_default_none() -> None:
    @dataclasses.dataclass
    class Dep:
        request: Request | None

    def factory(request: Request | None = None) -> Dep:
        return Dep(request=request)

    Injection = typing.Annotated[Dep, factory]

    def fn(dep: Injection) -> str:
        return dep.__class__.__name__ + dep.request.__class__.__name__

    app = Starlette()
    conn = Request({"type": "http"})
    plan = DependencyResolver.from_callable(fn)
    result = await plan.execute(InvokeContext(request=conn, app=app))
    assert result == "DepRequest"


async def test_not_supports_partial_functions() -> None:
    @dataclasses.dataclass
    class Dep:
        request: Request | None

    def factory(request: Request | None = None) -> Dep:  # pragma: nocover
        return Dep(request=request)

    Injection = typing.Annotated[Dep, factory]

    def fn(dep: Injection) -> str:  # pragma: nocover
        return dep.__class__.__name__ + dep.request.__class__.__name__

    with pytest.raises(InvalidDependency, match="Partial functions"):
        DependencyResolver.from_callable(functools.partial(fn))
