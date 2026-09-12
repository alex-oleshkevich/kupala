import contextlib
import inspect
import logging
import threading
import typing

import pytest
from starlette.datastructures import State

from kupala.dependencies import (
    MISSING,
    AmbiguousBindingError,
    CircularDependencyError,
    CompileContext,
    DependencyError,
    Factory,
    FromState,
    Inject,
    Injected,
    InjectionScope,
    InvalidDependencyError,
    InvocationContext,
    ParamInfo,
    UnannotatedParameterError,
    UnresolvedDependencyError,
    UnresolvedStateError,
    UnsupportedParameterError,
    Value,
    compile_call_plan,
    constant,
    find_binding,
    inspect_callable,
    invoke,
    parse_parameter,
    resolve_arguments,
)

type _ExampleDep = typing.Annotated[str, Value("demovalue")]
type _MaybeStr = str | None
type _MaybeDep = _ExampleDep | None
type _NestedDep = Injected[_ExampleDep]


class TestParseParameter:
    def test_scalar_param(self) -> None:
        param = inspect.Parameter("param", inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=str)

        assert parse_parameter(param) == ParamInfo(
            name="param",
            type=str,
            kind=inspect.Parameter.POSITIONAL_OR_KEYWORD,
            annotation=str,
            default=MISSING,
            metadata=(),
        )

    def test_unannotated_param(self) -> None:
        param = inspect.Parameter("param", inspect.Parameter.POSITIONAL_OR_KEYWORD)
        result = parse_parameter(param)

        assert result.type is MISSING
        assert result.annotation is MISSING
        assert result.default is MISSING

    def test_param_with_default(self) -> None:
        param = inspect.Parameter("param", inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=str, default="default")
        result = parse_parameter(param)

        assert result.default == "default"
        assert result.optional is True

    def test_optional_param_defaults_to_none(self) -> None:
        param = inspect.Parameter("param", inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=str | None)
        result = parse_parameter(param)

        assert result.type is str
        assert result.annotation == str | None
        assert result.default is None
        assert result.optional is True

    def test_optional_param_keeps_explicit_default(self) -> None:
        param = inspect.Parameter("param", inspect.Parameter.KEYWORD_ONLY, annotation=str | None, default="default")
        result = parse_parameter(param)

        assert result.type is str
        assert result.default == "default"

    def test_optional_alias_param(self) -> None:
        param = inspect.Parameter("param", inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=_MaybeStr)
        result = parse_parameter(param)

        assert result.type is str
        assert result.annotation is _MaybeStr
        assert result.default is None

    def test_keeps_raw_annotation_alongside_metadata(self) -> None:
        param = inspect.Parameter("param", inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=_ExampleDep)
        result = parse_parameter(param)

        assert result.type is str
        assert result.annotation is _ExampleDep
        assert result.metadata == (Value("demovalue"),)

    def test_finds_metadata_a_union_encloses(self) -> None:
        # `Query[str] | None` is a union whose member carries the binding, so one unwrap cannot see it
        param = inspect.Parameter("param", inspect.Parameter.KEYWORD_ONLY, annotation=_ExampleDep | None, default=None)
        result = parse_parameter(param)

        assert result.type is str
        assert result.metadata == (Value("demovalue"),)

    def test_finds_metadata_an_aliased_union_encloses(self) -> None:
        param = inspect.Parameter("param", inspect.Parameter.KEYWORD_ONLY, annotation=_MaybeDep)
        result = parse_parameter(param)

        assert result.type is str
        assert result.metadata == (Value("demovalue"),)
        assert result.default is None

    def test_records_parameter_kind(self) -> None:
        param = inspect.Parameter("kwargs", inspect.Parameter.VAR_KEYWORD, annotation=str)

        assert parse_parameter(param).kind is inspect.Parameter.VAR_KEYWORD


class TestInspectCallable:
    def test_inspect_callable_without_params(self) -> None:
        def fn() -> None:
            pass  # pragma: no cover

        result = inspect_callable(fn)
        assert result.callable is fn
        assert result.parameters == ()
        assert result.return_type is None

    def test_inspect_callable_with_scalar_param(self) -> None:
        def fn(param: str) -> None:
            pass  # pragma: no cover

        result = inspect_callable(fn)
        assert result.callable is fn
        assert result.parameters == (
            ParamInfo(
                name="param",
                type=str,
                default=MISSING,
                kind=inspect.Parameter.POSITIONAL_OR_KEYWORD,
                annotation=str,
                metadata=(),
            ),
        )
        assert result.return_type is None

    def test_inspect_callable_with_type_param(self) -> None:
        def fn(param: _ExampleDep) -> None:
            pass  # pragma: no cover

        result = inspect_callable(fn)
        assert result.callable is fn
        assert result.parameters == (
            ParamInfo(
                name="param",
                kind=inspect.Parameter.POSITIONAL_OR_KEYWORD,
                metadata=(Value("demovalue"),),
                annotation=_ExampleDep,
                default=MISSING,
                type=str,
            ),
        )
        assert result.return_type is None

    def test_inspect_callable_with_injected_param(self) -> None:
        def fn(param: Injected[str]) -> None:
            pass  # pragma: no cover

        result = inspect_callable(fn)
        assert result.parameters == (
            ParamInfo(
                name="param",
                kind=inspect.Parameter.POSITIONAL_OR_KEYWORD,
                metadata=(Inject(),),
                annotation=Injected[str],
                default=MISSING,
                type=str,
            ),
        )

    def test_inspect_callable_with_default_param(self) -> None:
        def fn(param: str = "default") -> None:
            pass  # pragma: no cover

        result = inspect_callable(fn)
        assert result.callable is fn
        assert result.parameters == (
            ParamInfo(
                name="param",
                type=str,
                default="default",
                kind=inspect.Parameter.POSITIONAL_OR_KEYWORD,
                annotation=str,
                metadata=(),
            ),
        )
        assert result.return_type is None

    def test_inspect_callable_with_optional_param(self) -> None:
        def fn(param: str | None) -> str:
            return ""  # pragma: no cover

        result = inspect_callable(fn)
        assert result.callable is fn
        assert result.parameters == (
            ParamInfo(
                name="param",
                type=str,
                default=None,
                kind=inspect.Parameter.POSITIONAL_OR_KEYWORD,
                annotation=str | None,
                metadata=(),
            ),
        )
        assert result.return_type is str

    def test_inspect_callable_with_return_value(self) -> None:
        def fn() -> str:
            return ""  # pragma: no cover

        result = inspect_callable(fn)
        assert result.callable is fn
        assert result.parameters == ()
        assert result.return_type is str

    def test_inspect_callable_without_return_annotation(self) -> None:
        def fn():  # type: ignore[no-untyped-def]
            pass  # pragma: no cover

        result = inspect_callable(fn)
        assert result.return_type is MISSING


class TestInjectionScope:
    def test_binds_resolver_by_type(self) -> None:
        scope = InjectionScope(bindings={})
        resolver = constant("demovalue")
        scope.bind(str, resolver)

        assert scope.bindings == {str: resolver}


class TestInvocationContext:
    async def test_resolves_bound_type(self) -> None:
        context = InvocationContext(scope=InjectionScope(bindings={str: constant("demovalue")}))

        assert await context.resolve(str) == "demovalue"

    async def test_falls_back_to_default(self) -> None:
        context = InvocationContext(scope=InjectionScope(bindings={}))

        assert await context.resolve(str, "fallback") == "fallback"

    async def test_prefers_binding_over_default(self) -> None:
        context = InvocationContext(scope=InjectionScope(bindings={str: constant("demovalue")}))

        assert await context.resolve(str, "fallback") == "demovalue"

    async def test_raises_without_binding_or_default(self) -> None:
        context = InvocationContext(scope=InjectionScope(bindings={}))

        with pytest.raises(UnresolvedDependencyError):
            await context.resolve(str)

    def test_starts_with_an_empty_cache(self) -> None:
        assert InvocationContext(scope=InjectionScope(bindings={})).cache == {}

    def test_starts_without_an_exit_stack(self) -> None:
        assert InvocationContext(scope=InjectionScope(bindings={})).exit_stack is None

    async def test_opens_the_exit_stack_on_entry(self) -> None:
        context = InvocationContext(scope=InjectionScope(bindings={}))

        async with context as entered:
            assert entered is context
            assert context.exit_stack is not None

    async def test_forgets_the_exit_stack_on_exit(self) -> None:
        context = InvocationContext(scope=InjectionScope(bindings={}))

        async with context:
            pass

        assert context.exit_stack is None

    async def test_unwinds_callbacks_in_reverse_order(self) -> None:
        events: list[str] = []
        context = InvocationContext(scope=InjectionScope(bindings={}))

        async with context:
            assert context.exit_stack is not None
            context.exit_stack.callback(events.append, "first")
            context.exit_stack.callback(events.append, "second")

        assert events == ["second", "first"]

    async def test_logs_and_swallows_a_failing_callback(self, caplog: pytest.LogCaptureFixture) -> None:
        def boom() -> None:
            raise RuntimeError("teardown failed")

        context = InvocationContext(scope=InjectionScope(bindings={}))

        with caplog.at_level(logging.ERROR, logger="kupala.dependencies"):
            async with context:
                assert context.exit_stack is not None
                context.exit_stack.callback(boom)

        assert "teardown failed" in caplog.text

    async def test_propagates_an_error_raised_inside_the_block(self) -> None:
        context = InvocationContext(scope=InjectionScope(bindings={}))

        with pytest.raises(RuntimeError, match="boom"):
            async with context:
                raise RuntimeError("boom")

    async def test_does_not_log_an_error_that_only_passes_through(self, caplog: pytest.LogCaptureFixture) -> None:
        # the block's own error travels back out through every registered generator,
        # and re-emerging unchanged is not a teardown failure
        def resource() -> typing.Iterator[str]:
            yield "demovalue"

        context = InvocationContext(scope=InjectionScope(bindings={}))

        with (
            caplog.at_level(logging.ERROR, logger="kupala.dependencies"),
            pytest.raises(RuntimeError, match="boom"),
        ):
            async with context:
                assert context.exit_stack is not None
                context.exit_stack.enter_context(contextlib.contextmanager(resource)())
                raise RuntimeError("boom")

        assert caplog.text == ""


class TestFindBinding:
    def test_returns_binding_from_metadata(self) -> None:
        param = inspect.Parameter("param", inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=_ExampleDep)

        assert find_binding(parse_parameter(param), "demo.fn") == Value("demovalue")

    def test_defaults_to_inject(self) -> None:
        param = inspect.Parameter("param", inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=str)

        assert find_binding(parse_parameter(param), "demo.fn") == Inject()

    def test_skips_plain_metadata(self) -> None:
        annotation = typing.Annotated[str, "note", Value("demovalue")]
        param = inspect.Parameter("param", inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=annotation)

        assert find_binding(parse_parameter(param), "demo.fn") == Value("demovalue")

    def test_ignores_binding_classes(self) -> None:
        param = inspect.Parameter(
            "param", inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=typing.Annotated[str, Value]
        )

        assert find_binding(parse_parameter(param), "demo.fn") == Inject()

    def test_rejects_two_bindings(self) -> None:
        annotation = typing.Annotated[str, Value("first"), Value("second")]
        param = inspect.Parameter("param", inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=annotation)

        with pytest.raises(AmbiguousBindingError):
            find_binding(parse_parameter(param), "demo.fn")

    def test_rejects_injected_wrapping_a_bound_alias(self) -> None:
        # `Injected[_ExampleDep]` flattens to (Value(...), Inject()), so the alias already carries its binding
        param = inspect.Parameter("param", inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=_NestedDep)

        with pytest.raises(AmbiguousBindingError):
            find_binding(parse_parameter(param), "demo.fn")

    def test_names_the_parameter_and_owner(self) -> None:
        annotation = typing.Annotated[str, Value("first"), Value("second")]
        param = inspect.Parameter("param", inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=annotation)

        with pytest.raises(AmbiguousBindingError) as info:
            find_binding(parse_parameter(param), "demo.fn")

        message = str(info.value)
        assert "Parameter 'param' of demo.fn() has 2 bindings: Value, Value." in message
        assert "Annotate it with exactly one." in message
        # a bound value may hold a secret, so only the binding types are named
        assert "first" not in message

    def test_is_an_invalid_dependency_error(self) -> None:
        assert issubclass(AmbiguousBindingError, InvalidDependencyError)


class TestCompileCallPlan:
    def test_compiles_a_resolver_per_parameter(self) -> None:
        def fn(user: Injected[str], greeting: typing.Annotated[str, Value("hello")]) -> str:
            return f"{greeting} {user}"  # pragma: no cover

        plan = compile_call_plan(fn)

        assert plan.callable.callable is fn
        assert [parameter.param.name for parameter in plan.parameters] == ["user", "greeting"]

    def test_compiles_callable_without_parameters(self) -> None:
        def fn() -> str:
            return "demovalue"  # pragma: no cover

        assert compile_call_plan(fn).parameters == ()


class TestInvoke:
    async def test_invokes_async_callable(self) -> None:
        async def fn(user: Injected[str]) -> str:
            return f"hello {user}"

        context = InvocationContext(scope=InjectionScope(bindings={str: constant("alex")}))

        assert await invoke(compile_call_plan(fn), context) == "hello alex"

    async def test_invokes_sync_callable(self) -> None:
        def fn(user: Injected[str]) -> str:
            return f"hello {user}"

        context = InvocationContext(scope=InjectionScope(bindings={str: constant("alex")}))

        assert await invoke(compile_call_plan(fn), context) == "hello alex"

    async def test_resolves_value_metadata_without_bindings(self) -> None:
        def fn(greeting: typing.Annotated[str, Value("hello")]) -> str:
            return greeting

        context = InvocationContext(scope=InjectionScope(bindings={}))

        assert await invoke(compile_call_plan(fn), context) == "hello"

    async def test_uses_parameter_default_when_unbound(self) -> None:
        def fn(page: int = 1) -> int:
            return page

        context = InvocationContext(scope=InjectionScope(bindings={}))

        assert await invoke(compile_call_plan(fn), context) == 1

    async def test_resolves_optional_to_none_when_unbound(self) -> None:
        def fn(tag: str | None) -> str | None:
            return tag

        context = InvocationContext(scope=InjectionScope(bindings={}))

        assert await invoke(compile_call_plan(fn), context) is None

    async def test_runs_sync_callable_in_a_worker_thread(self) -> None:
        def fn() -> int:
            return threading.get_ident()

        context = InvocationContext(scope=InjectionScope(bindings={}))

        assert await invoke(compile_call_plan(fn), context) != threading.get_ident()

    async def test_runs_async_callable_on_the_event_loop(self) -> None:
        async def fn() -> int:
            return threading.get_ident()

        context = InvocationContext(scope=InjectionScope(bindings={}))

        assert await invoke(compile_call_plan(fn), context) == threading.get_ident()

    async def test_raises_for_unresolvable_parameter(self) -> None:
        def fn(user: Injected[str]) -> str:
            return user  # pragma: no cover

        context = InvocationContext(scope=InjectionScope(bindings={}))

        with pytest.raises(UnresolvedDependencyError):
            await invoke(compile_call_plan(fn), context)


class TestPositionalOnlyParameters:
    """A parameter before `/` is resolved by type like any other; only the handover differs."""

    async def test_passes_a_positional_only_parameter_by_position(self) -> None:
        async def fn(user: Injected[str], /) -> str:
            return f"hello {user}"

        context = InvocationContext(scope=InjectionScope(bindings={str: constant("alex")}))

        assert await invoke(compile_call_plan(fn), context) == "hello alex"

    async def test_passes_a_positional_only_parameter_to_a_sync_callable(self) -> None:
        def fn(user: Injected[str], /) -> str:
            return f"hello {user}"

        context = InvocationContext(scope=InjectionScope(bindings={str: constant("alex")}))

        assert await invoke(compile_call_plan(fn), context) == "hello alex"

    async def test_keeps_signature_order_across_the_slash(self) -> None:
        async def fn(
            first: Injected[str],
            second: Injected[int],
            /,
            third: Injected[bytes],
            *,
            fourth: Injected[float],
        ) -> str:
            return f"{first} {second} {third!r} {fourth}"

        context = InvocationContext(
            scope=InjectionScope(
                bindings={
                    str: constant("a"),
                    int: constant(2),
                    bytes: constant(b"c"),
                    float: constant(0.5),
                }
            ),
        )

        assert await invoke(compile_call_plan(fn), context) == "a 2 b'c' 0.5"

    def test_reports_no_positional_names_without_a_slash(self) -> None:
        def fn(user: Injected[str]) -> str:
            return user  # pragma: no cover

        info = inspect_callable(fn)

        assert info.positional_names == ()
        assert info.bind({"user": "alex"}) == ((), {"user": "alex"})

    def test_splits_resolved_arguments_at_the_slash(self) -> None:
        def fn(user: Injected[str], /, page: Injected[int]) -> str:
            return user  # pragma: no cover

        info = inspect_callable(fn)

        assert info.positional_names == ("user",)
        assert info.bind({"user": "alex", "page": 2}) == (("alex",), {"page": 2})

    async def test_opens_an_async_context_manager_factory_by_position(self) -> None:
        @contextlib.asynccontextmanager
        async def make(user: Injected[str], /) -> typing.AsyncIterator[str]:
            yield f"session for {user}"

        def fn(value: typing.Annotated[str, Factory(make)]) -> str:
            return value

        context = InvocationContext(scope=InjectionScope(bindings={str: constant("alex")}))

        async with context:
            assert await invoke(compile_call_plan(fn), context) == "session for alex"

    async def test_opens_a_sync_context_manager_factory_by_position(self) -> None:
        @contextlib.contextmanager
        def make(user: Injected[str], /) -> typing.Iterator[str]:
            yield f"session for {user}"

        def fn(value: typing.Annotated[str, Factory(make)]) -> str:
            return value

        context = InvocationContext(scope=InjectionScope(bindings={str: constant("alex")}))

        async with context:
            assert await invoke(compile_call_plan(fn), context) == "session for alex"


class TestCallableInfoIsAsync:
    def test_records_async_callable(self) -> None:
        async def fn() -> None:
            pass  # pragma: no cover

        assert inspect_callable(fn).is_async is True

    def test_records_sync_callable(self) -> None:
        def fn() -> None:
            pass  # pragma: no cover

        assert inspect_callable(fn).is_async is False


class TestValidateParameter:
    def test_allows_positional_only_parameter(self) -> None:
        def fn(param: str, /) -> None:
            pass  # pragma: no cover

        assert compile_call_plan(fn).parameters[0].param.name == "param"

    def test_rejects_unannotated_positional_only_parameter(self) -> None:
        def fn(param, /) -> None:  # type: ignore[no-untyped-def]
            pass  # pragma: no cover

        with pytest.raises(UnannotatedParameterError) as info:
            compile_call_plan(fn)

        assert "has no type annotation" in str(info.value)

    def test_rejects_variadic_positional_parameter(self) -> None:
        def fn(*args: str) -> None:
            pass  # pragma: no cover

        with pytest.raises(UnsupportedParameterError) as info:
            compile_call_plan(fn)

        assert "Cannot inject parameter 'args'" in str(info.value)
        assert "test_rejects_variadic_positional_parameter.<locals>.fn()" in str(info.value)
        assert "*args is never filled" in str(info.value)

    def test_rejects_variadic_keyword_parameter(self) -> None:
        def fn(**kwargs: str) -> None:
            pass  # pragma: no cover

        with pytest.raises(UnsupportedParameterError) as info:
            compile_call_plan(fn)

        assert "**kwargs is never filled" in str(info.value)

    def test_rejects_unannotated_parameter(self) -> None:
        def fn(param) -> None:  # type: ignore[no-untyped-def]
            pass  # pragma: no cover

        with pytest.raises(UnannotatedParameterError) as info:
            compile_call_plan(fn)

        assert "has no type annotation" in str(info.value)

    def test_allows_unannotated_parameter_with_default(self) -> None:
        def fn(param="default") -> None:  # type: ignore[no-untyped-def]
            pass  # pragma: no cover

        assert compile_call_plan(fn).parameters[0].param.name == "param"

    def test_keyword_only_parameter_is_supported(self) -> None:
        def fn(*, param: str) -> None:
            pass  # pragma: no cover

        assert compile_call_plan(fn).parameters[0].param.name == "param"


class TestUnresolvedDependencyError:
    async def test_names_the_key_parameter_and_callable(self) -> None:
        def fn(param: complex) -> None:
            pass  # pragma: no cover

        context = InvocationContext(scope=InjectionScope(bindings={}))

        with pytest.raises(UnresolvedDependencyError) as info:
            await invoke(compile_call_plan(fn), context)

        message = str(info.value)
        assert "No binding for complex" in message
        assert "parameter 'param'" in message
        assert "test_names_the_key_parameter_and_callable.<locals>.fn()" in message

    async def test_reports_the_key_when_resolved_directly(self) -> None:
        context = InvocationContext(scope=InjectionScope(bindings={}))

        with pytest.raises(UnresolvedDependencyError) as info:
            await context.resolve(complex)

        assert str(info.value).startswith("No binding for complex.")

    def test_is_a_dependency_error(self) -> None:
        assert issubclass(UnsupportedParameterError, InvalidDependencyError)
        assert issubclass(InvalidDependencyError, DependencyError)
        assert issubclass(UnresolvedDependencyError, DependencyError)

    def test_names_the_parameter_without_a_callable(self) -> None:
        error = UnresolvedDependencyError(complex, parameter="param")

        assert str(error) == (
            "No binding for complex requested by parameter 'param'. "
            "Bind it on the injection scope, or give the parameter a default value."
        )


class TestCompileContext:
    def test_starts_without_a_chain(self) -> None:
        assert CompileContext().chain == ()

    def test_enter_extends_the_chain(self) -> None:
        def make() -> str:
            return "demovalue"  # pragma: no cover

        factory = Factory(make)

        assert CompileContext().enter(factory).chain == (factory,)

    def test_enter_appends_to_an_existing_chain(self) -> None:
        def make_outer() -> str:
            return "outer"  # pragma: no cover

        def make_inner() -> str:
            return "inner"  # pragma: no cover

        outer, inner = Factory(make_outer), Factory(make_inner)

        assert CompileContext().enter(outer).enter(inner).chain == (outer, inner)

    def test_enter_leaves_the_parent_untouched(self) -> None:
        def make() -> str:
            return "demovalue"  # pragma: no cover

        parent = CompileContext()
        parent.enter(Factory(make))

        assert parent.chain == ()

    def test_finds_an_equal_factory_in_the_chain(self) -> None:
        # cycle detection and cache identity must agree, so both compare by value
        def make() -> str:
            return "demovalue"  # pragma: no cover

        context = CompileContext().enter(Factory(make))

        assert Factory(make) in context.chain


class TestResolveArguments:
    async def test_resolves_every_parameter_by_name(self) -> None:
        def fn(user: Injected[str], greeting: typing.Annotated[str, Value("hello")]) -> str:
            return f"{greeting} {user}"  # pragma: no cover

        context = InvocationContext(scope=InjectionScope(bindings={str: constant("alex")}))

        assert await resolve_arguments(compile_call_plan(fn), context) == {"user": "alex", "greeting": "hello"}

    async def test_returns_an_empty_mapping_without_parameters(self) -> None:
        def fn() -> str:
            return "demovalue"  # pragma: no cover

        context = InvocationContext(scope=InjectionScope(bindings={}))

        assert await resolve_arguments(compile_call_plan(fn), context) == {}

    async def test_names_the_owner_when_a_parameter_is_unresolvable(self) -> None:
        def fn(param: complex) -> None:
            pass  # pragma: no cover

        context = InvocationContext(scope=InjectionScope(bindings={}))

        with pytest.raises(UnresolvedDependencyError) as info:
            await resolve_arguments(compile_call_plan(fn), context)

        assert "test_names_the_owner_when_a_parameter_is_unresolvable.<locals>.fn()" in str(info.value)


class TestFactory:
    async def test_calls_sync_factory(self) -> None:
        def make() -> str:
            return "demovalue"

        def fn(value: typing.Annotated[str, Factory(make)]) -> str:
            return value

        context = InvocationContext(scope=InjectionScope(bindings={}))

        async with context:
            assert await invoke(compile_call_plan(fn), context) == "demovalue"

    async def test_runs_sync_factory_in_a_worker_thread(self) -> None:
        def make() -> int:
            return threading.get_ident()

        def fn(value: typing.Annotated[int, Factory(make)]) -> int:
            return value

        context = InvocationContext(scope=InjectionScope(bindings={}))

        async with context:
            assert await invoke(compile_call_plan(fn), context) != threading.get_ident()

    async def test_calls_async_factory(self) -> None:
        async def make() -> str:
            return "demovalue"

        def fn(value: typing.Annotated[str, Factory(make)]) -> str:
            return value

        context = InvocationContext(scope=InjectionScope(bindings={}))

        async with context:
            assert await invoke(compile_call_plan(fn), context) == "demovalue"

    async def test_enters_sync_context_manager(self) -> None:
        @contextlib.contextmanager
        def make() -> typing.Iterator[str]:
            yield "demovalue"

        def fn(value: typing.Annotated[str, Factory(make)]) -> str:
            return value

        context = InvocationContext(scope=InjectionScope(bindings={}))

        async with context:
            assert await invoke(compile_call_plan(fn), context) == "demovalue"

    async def test_closes_sync_context_manager_when_the_context_exits(self) -> None:
        events: list[str] = []

        @contextlib.contextmanager
        def make() -> typing.Iterator[str]:
            yield "demovalue"
            events.append("closed")

        def fn(value: typing.Annotated[str, Factory(make)]) -> str:
            return value

        context = InvocationContext(scope=InjectionScope(bindings={}))

        async with context:
            await invoke(compile_call_plan(fn), context)
            assert events == []

        assert events == ["closed"]

    async def test_runs_sync_context_manager_in_a_worker_thread(self) -> None:
        threads: list[int] = []

        @contextlib.contextmanager
        def make() -> typing.Iterator[str]:
            threads.append(threading.get_ident())
            yield "demovalue"
            threads.append(threading.get_ident())

        def fn(value: typing.Annotated[str, Factory(make)]) -> str:
            return value

        context = InvocationContext(scope=InjectionScope(bindings={}))

        async with context:
            await invoke(compile_call_plan(fn), context)

        assert len(threads) == 2
        assert all(thread != threading.get_ident() for thread in threads)

    async def test_enters_async_context_manager(self) -> None:
        @contextlib.asynccontextmanager
        async def make() -> typing.AsyncIterator[str]:
            yield "demovalue"

        def fn(value: typing.Annotated[str, Factory(make)]) -> str:
            return value

        context = InvocationContext(scope=InjectionScope(bindings={}))

        async with context:
            assert await invoke(compile_call_plan(fn), context) == "demovalue"

    async def test_closes_async_context_manager_when_the_context_exits(self) -> None:
        events: list[str] = []

        @contextlib.asynccontextmanager
        async def make() -> typing.AsyncIterator[str]:
            yield "demovalue"
            events.append("closed")

        def fn(value: typing.Annotated[str, Factory(make)]) -> str:
            return value

        context = InvocationContext(scope=InjectionScope(bindings={}))

        async with context:
            await invoke(compile_call_plan(fn), context)
            assert events == []

        assert events == ["closed"]

    async def test_closes_context_managers_in_reverse_order(self) -> None:
        events: list[str] = []

        @contextlib.contextmanager
        def make_first() -> typing.Iterator[str]:
            yield "first"
            events.append("first")

        @contextlib.contextmanager
        def make_second() -> typing.Iterator[str]:
            yield "second"
            events.append("second")

        def fn(
            first: typing.Annotated[str, Factory(make_first)],
            second: typing.Annotated[str, Factory(make_second)],
        ) -> str:
            return f"{first} {second}"

        context = InvocationContext(scope=InjectionScope(bindings={}))

        async with context:
            assert await invoke(compile_call_plan(fn), context) == "first second"

        assert events == ["second", "first"]

    async def test_passes_an_escaping_error_to_the_context_manager(self) -> None:
        seen: list[str] = []

        @contextlib.contextmanager
        def make() -> typing.Iterator[str]:
            try:
                yield "demovalue"
            except RuntimeError as exc:
                seen.append(str(exc))
                raise

        def fn(value: typing.Annotated[str, Factory(make)]) -> str:
            return value

        context = InvocationContext(scope=InjectionScope(bindings={}))

        with pytest.raises(RuntimeError, match="boom"):
            async with context:
                await invoke(compile_call_plan(fn), context)
                raise RuntimeError("boom")

        assert seen == ["boom"]

    async def test_a_context_manager_cannot_swallow_an_escaping_error(self) -> None:
        @contextlib.contextmanager
        def make() -> typing.Iterator[str]:
            try:
                yield "demovalue"
            except RuntimeError:
                pass  # a dependency must not be able to hide the caller's failure

        def fn(value: typing.Annotated[str, Factory(make)]) -> str:
            return value

        context = InvocationContext(scope=InjectionScope(bindings={}))

        with pytest.raises(RuntimeError, match="boom"):
            async with context:
                await invoke(compile_call_plan(fn), context)
                raise RuntimeError("boom")

    async def test_caches_the_value_by_default(self) -> None:
        calls: list[int] = []

        def make() -> int:
            calls.append(1)
            return len(calls)

        def fn(
            first: typing.Annotated[int, Factory(make)],
            second: typing.Annotated[int, Factory(make)],
        ) -> tuple[int, int]:
            return first, second

        context = InvocationContext(scope=InjectionScope(bindings={}))

        async with context:
            assert await invoke(compile_call_plan(fn), context) == (1, 1)

        assert len(calls) == 1

    async def test_builds_each_time_when_caching_is_off(self) -> None:
        calls: list[int] = []

        def make() -> int:
            calls.append(1)
            return len(calls)

        def fn(
            first: typing.Annotated[int, Factory(make, cache=False)],
            second: typing.Annotated[int, Factory(make, cache=False)],
        ) -> tuple[int, int]:
            return first, second

        context = InvocationContext(scope=InjectionScope(bindings={}))

        async with context:
            assert await invoke(compile_call_plan(fn), context) == (1, 2)

        assert len(calls) == 2

    async def test_registers_one_teardown_for_a_cached_context_manager(self) -> None:
        events: list[str] = []

        @contextlib.contextmanager
        def make() -> typing.Iterator[str]:
            yield "demovalue"
            events.append("closed")

        def fn(
            first: typing.Annotated[str, Factory(make)],
            second: typing.Annotated[str, Factory(make)],
        ) -> str:
            return f"{first} {second}"

        context = InvocationContext(scope=InjectionScope(bindings={}))

        async with context:
            await invoke(compile_call_plan(fn), context)

        assert events == ["closed"]

    async def test_propagates_an_error_raised_by_the_factory(self) -> None:
        def make() -> str:
            raise RuntimeError("factory failed")

        def fn(value: typing.Annotated[str, Factory(make)]) -> str:
            return value  # pragma: no cover

        context = InvocationContext(scope=InjectionScope(bindings={}))

        with pytest.raises(RuntimeError, match="factory failed"):
            async with context:
                await invoke(compile_call_plan(fn), context)

    async def test_names_the_factory_whose_signature_is_invalid(self) -> None:
        # the innermost callable names itself, so a broken factory is not blamed on its dependent
        def make(*args: str) -> str:
            return "".join(args)  # pragma: no cover

        def fn(value: typing.Annotated[str, Factory(make)]) -> str:
            return value  # pragma: no cover

        with pytest.raises(UnsupportedParameterError) as info:
            compile_call_plan(fn)

        assert "test_names_the_factory_whose_signature_is_invalid.<locals>.make()" in str(info.value)

    async def test_registers_every_teardown_when_caching_is_off(self) -> None:
        events: list[str] = []

        @contextlib.contextmanager
        def make() -> typing.Iterator[str]:
            yield "demovalue"
            events.append("closed")

        def fn(
            first: typing.Annotated[str, Factory(make, cache=False)],
            second: typing.Annotated[str, Factory(make, cache=False)],
        ) -> str:
            return f"{first} {second}"

        context = InvocationContext(scope=InjectionScope(bindings={}))

        async with context:
            await invoke(compile_call_plan(fn), context)

        assert events == ["closed", "closed"]

    async def test_resolves_the_factory_own_parameters(self) -> None:
        def make(user: Injected[str]) -> str:
            return f"hello {user}"

        def fn(value: typing.Annotated[str, Factory(make)]) -> str:
            return value

        context = InvocationContext(scope=InjectionScope(bindings={str: constant("alex")}))

        async with context:
            assert await invoke(compile_call_plan(fn), context) == "hello alex"

    async def test_resolves_a_factory_that_depends_on_a_factory(self) -> None:
        def make_inner() -> str:
            return "inner"

        def make_outer(inner: typing.Annotated[str, Factory(make_inner)]) -> str:
            return f"outer({inner})"

        def fn(value: typing.Annotated[str, Factory(make_outer)]) -> str:
            return value

        context = InvocationContext(scope=InjectionScope(bindings={}))

        async with context:
            assert await invoke(compile_call_plan(fn), context) == "outer(inner)"

    async def test_shares_a_cached_factory_between_dependents(self) -> None:
        calls: list[int] = []

        def make_base() -> int:
            calls.append(1)
            return 7

        def make_left(base: typing.Annotated[int, Factory(make_base)]) -> str:
            return f"left{base}"

        def make_right(base: typing.Annotated[int, Factory(make_base)]) -> str:
            return f"right{base}"

        def fn(
            left: typing.Annotated[str, Factory(make_left)],
            right: typing.Annotated[str, Factory(make_right)],
        ) -> str:
            return f"{left} {right}"

        context = InvocationContext(scope=InjectionScope(bindings={}))

        async with context:
            assert await invoke(compile_call_plan(fn), context) == "left7 right7"

        assert len(calls) == 1

    async def test_names_the_factory_when_its_dependency_is_missing(self) -> None:
        def make(param: complex) -> str:
            return str(param)  # pragma: no cover

        def fn(value: typing.Annotated[str, Factory(make)]) -> str:
            return value  # pragma: no cover

        context = InvocationContext(scope=InjectionScope(bindings={}))

        with pytest.raises(UnresolvedDependencyError) as info:
            async with context:
                await invoke(compile_call_plan(fn), context)

        assert "test_names_the_factory_when_its_dependency_is_missing.<locals>.make()" in str(info.value)

    async def test_requires_an_entered_context_for_context_managers(self) -> None:
        @contextlib.contextmanager
        def make() -> typing.Iterator[str]:
            yield "demovalue"  # pragma: no cover

        def fn(value: typing.Annotated[str, Factory(make)]) -> str:
            return value  # pragma: no cover

        context = InvocationContext(scope=InjectionScope(bindings={}))

        with pytest.raises(DependencyError, match="outside an active invocation context"):
            await invoke(compile_call_plan(fn), context)

    async def test_does_not_require_an_entered_context_for_plain_factories(self) -> None:
        def make() -> str:
            return "demovalue"

        def fn(value: typing.Annotated[str, Factory(make)]) -> str:
            return value

        context = InvocationContext(scope=InjectionScope(bindings={}))

        assert await invoke(compile_call_plan(fn), context) == "demovalue"

    async def test_seeded_cache_entry_overrides_the_factory(self) -> None:
        def make() -> str:
            return "real"  # pragma: no cover

        def fn(value: typing.Annotated[str, Factory(make)]) -> str:
            return value

        context = InvocationContext(scope=InjectionScope(bindings={}))
        context.cache[Factory(make)] = "override"

        async with context:
            assert await invoke(compile_call_plan(fn), context) == "override"

    def test_equal_factories_share_a_cache_key(self) -> None:
        def make() -> str:
            return "demovalue"  # pragma: no cover

        assert Factory(make) == Factory(make)
        assert hash(Factory(make)) == hash(Factory(make))

    def test_caching_is_part_of_the_cache_key(self) -> None:
        def make() -> str:
            return "demovalue"  # pragma: no cover

        assert Factory(make) != Factory(make, cache=False)


class TestCircularDependency:
    async def test_rejects_a_cycle_between_registered_resolvers(self) -> None:
        async def resolve_text(context: InvocationContext) -> object:
            return await context.resolve(bytes)

        async def resolve_bytes(context: InvocationContext) -> object:
            return await context.resolve(str)

        context = InvocationContext(
            scope=InjectionScope(bindings={str: resolve_text, bytes: resolve_bytes}),
        )

        with pytest.raises(CircularDependencyError, match="str -> bytes -> str"):
            await context.resolve(str)

        assert context.resolving == []

    def test_rejects_a_factory_that_depends_on_itself(self) -> None:
        def make(inner: typing.Annotated[str, Factory(make)]) -> str:
            return inner  # pragma: no cover

        def fn(value: typing.Annotated[str, Factory(make)]) -> str:
            return value  # pragma: no cover

        with pytest.raises(CircularDependencyError):
            compile_call_plan(fn)

    def test_rejects_a_two_step_cycle(self) -> None:
        def make_a(b: typing.Annotated[str, Factory(make_b)]) -> str:
            return b  # pragma: no cover

        def make_b(a: typing.Annotated[str, Factory(make_a)]) -> str:
            return a  # pragma: no cover

        def fn(value: typing.Annotated[str, Factory(make_a)]) -> str:
            return value  # pragma: no cover

        with pytest.raises(CircularDependencyError):
            compile_call_plan(fn)

    def test_renders_the_whole_path(self) -> None:
        def make_a(b: typing.Annotated[str, Factory(make_b)]) -> str:
            return b  # pragma: no cover

        def make_b(a: typing.Annotated[str, Factory(make_a)]) -> str:
            return a  # pragma: no cover

        def fn(value: typing.Annotated[str, Factory(make_a)]) -> str:
            return value  # pragma: no cover

        with pytest.raises(CircularDependencyError) as info:
            compile_call_plan(fn)

        message = str(info.value)
        assert "test_renders_the_whole_path.<locals>.make_a" in message
        assert "test_renders_the_whole_path.<locals>.make_b" in message
        assert " -> " in message

    def test_accepts_a_diamond(self) -> None:
        def make_base() -> str:
            return "base"  # pragma: no cover

        def make_left(base: typing.Annotated[str, Factory(make_base)]) -> str:
            return base  # pragma: no cover

        def make_right(base: typing.Annotated[str, Factory(make_base)]) -> str:
            return base  # pragma: no cover

        def fn(
            left: typing.Annotated[str, Factory(make_left)],
            right: typing.Annotated[str, Factory(make_right)],
        ) -> str:
            return f"{left} {right}"  # pragma: no cover

        assert len(compile_call_plan(fn).parameters) == 2

    def test_is_an_invalid_dependency_error(self) -> None:
        assert issubclass(CircularDependencyError, InvalidDependencyError)


class TestOverrides:
    async def test_replaces_the_binding_of_an_annotation(self) -> None:
        type Greeting = typing.Annotated[str, Value("real")]

        def fn(greeting: Greeting) -> str:
            return greeting

        context = InvocationContext(scope=InjectionScope(bindings={}), overrides={Greeting: Value("fake")})

        assert await invoke(compile_call_plan(fn), context) == "fake"

    async def test_leaves_other_parameters_alone(self) -> None:
        type Greeting = typing.Annotated[str, Value("real")]
        type Subject = typing.Annotated[str, Value("world")]

        def fn(greeting: Greeting, subject: Subject) -> str:
            return f"{greeting} {subject}"

        context = InvocationContext(scope=InjectionScope(bindings={}), overrides={Greeting: Value("fake")})

        assert await invoke(compile_call_plan(fn), context) == "fake world"

    async def test_replaces_a_binding_that_never_caches(self) -> None:
        # a cache=False factory keeps no cache entry, so an override is the only way to reach it
        def make() -> str:
            return "real"  # pragma: no cover

        type Uncached = typing.Annotated[str, Factory(make, cache=False)]

        def fn(value: Uncached) -> str:
            return value

        context = InvocationContext(scope=InjectionScope(bindings={}), overrides={Uncached: Value("fake")})

        assert await invoke(compile_call_plan(fn), context) == "fake"

    async def test_replaces_with_a_context_manager_factory(self) -> None:
        events: list[str] = []

        def real() -> str:
            return "real"  # pragma: no cover

        @contextlib.contextmanager
        def fake() -> typing.Iterator[str]:
            yield "fake"
            events.append("released")

        type Greeting = typing.Annotated[str, Factory(real)]

        def fn(greeting: Greeting) -> str:
            return greeting

        context = InvocationContext(scope=InjectionScope(bindings={}), overrides={Greeting: Factory(fake)})

        async with context:
            assert await invoke(compile_call_plan(fn), context) == "fake"
            assert events == []

        # the replacement is released with the invocation, exactly like the binding it stands in for
        assert events == ["released"]


class TestFromState:
    async def test_selects_a_value_off_the_invocation_state(self) -> None:
        def fn(db: typing.Annotated[str, FromState(lambda ctx, state: state.db)]) -> str:
            return db

        context = InvocationContext(scope=InjectionScope(bindings={}), state=State({"db": "session"}))

        assert await invoke(compile_call_plan(fn), context) == "session"

    async def test_the_selector_can_derive_a_value(self) -> None:
        def fn(name: typing.Annotated[str, FromState(lambda ctx, state: state.db.upper())]) -> str:
            return name

        context = InvocationContext(scope=InjectionScope(bindings={}), state=State({"db": "session"}))

        assert await invoke(compile_call_plan(fn), context) == "SESSION"

    async def test_the_selector_receives_the_context(self) -> None:
        def fn(bound: typing.Annotated[InvocationContext, FromState(lambda ctx, state: ctx)]) -> InvocationContext:
            return bound

        context = InvocationContext(scope=InjectionScope(bindings={}), state=State({}))

        assert await invoke(compile_call_plan(fn), context) is context

    async def test_reports_what_the_state_does_not_have(self) -> None:
        def fn(db: typing.Annotated[str, FromState(lambda ctx, state: state.db)]) -> str:
            return db  # pragma: no cover

        context = InvocationContext(scope=InjectionScope(bindings={}), state=State({}))

        with pytest.raises(UnresolvedStateError) as info:
            await invoke(compile_call_plan(fn), context)

        message = str(info.value)
        assert "Parameter 'db' reads something the invocation state does not have" in message
        assert "Set it in the application lifespan or in a middleware." in message

    async def test_starts_with_empty_state(self) -> None:
        # a context built without state still resolves, so a command can be invoked bare
        assert InvocationContext(scope=InjectionScope(bindings={})).state._state == {}

    def test_is_a_dependency_error(self) -> None:
        assert issubclass(UnresolvedStateError, DependencyError)
