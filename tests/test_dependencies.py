import inspect
import threading
import typing

import pytest

from kupala.dependencies import (
    MISSING,
    DependencyError,
    Inject,
    Injected,
    InjectionScope,
    InvalidDependencyError,
    InvocationContext,
    ParamInfo,
    UnannotatedParameterError,
    UnresolvedDependencyError,
    UnsupportedParameterError,
    Value,
    compile_call_plan,
    find_binding,
    inspect_callable,
    invoke,
    is_async_callable,
    is_optional,
    parse_parameter,
    strip_none,
    unwrap_alias,
    unwrap_annotation,
)

type _ExampleDep = typing.Annotated[str, Value("demovalue")]
type _AliasOfAlias = _ExampleDep
type _MaybeStr = str | None
type _NestedDep = Injected[_ExampleDep]


class TestUnwrapAlias:
    def test_returns_plain_type_unchanged(self) -> None:
        assert unwrap_alias(str) is str

    def test_resolves_bare_alias(self) -> None:
        assert unwrap_alias(_ExampleDep) == typing.Annotated[str, Value("demovalue")]

    def test_resolves_chained_alias(self) -> None:
        assert unwrap_alias(_AliasOfAlias) == typing.Annotated[str, Value("demovalue")]

    def test_resolves_subscripted_alias(self) -> None:
        assert unwrap_alias(Injected[str]) == typing.Annotated[str, Inject()]

    def test_resolves_union_alias(self) -> None:
        assert unwrap_alias(_MaybeStr) == str | None


class TestUnwrapAnnotation:
    def test_plain_type_carries_no_metadata(self) -> None:
        assert unwrap_annotation(str) == (str, ())

    def test_extracts_metadata_from_alias(self) -> None:
        assert unwrap_annotation(_ExampleDep) == (str, (Value("demovalue"),))

    def test_extracts_metadata_from_subscripted_alias(self) -> None:
        assert unwrap_annotation(Injected[str]) == (str, (Inject(),))

    def test_merges_nested_metadata_innermost_first(self) -> None:
        assert unwrap_annotation(_NestedDep) == (str, (Value("demovalue"), Inject()))

    def test_keeps_every_metadata_entry(self) -> None:
        assert unwrap_annotation(typing.Annotated[str, "first", "second"]) == (str, ("first", "second"))

    def test_keeps_optional_union_intact(self) -> None:
        assert unwrap_annotation(typing.Annotated[str | None, Value("demovalue")]) == (
            str | None,
            (Value("demovalue"),),
        )


class TestIsOptional:
    def test_detects_none_union(self) -> None:
        assert is_optional(str | None) is True

    def test_detects_optional_alias_once_unwrapped(self) -> None:
        assert is_optional(unwrap_annotation(_MaybeStr)[0]) is True

    def test_ignores_plain_type(self) -> None:
        assert is_optional(str) is False

    def test_ignores_union_without_none(self) -> None:
        assert is_optional(str | int) is False


class TestStripNone:
    def test_collapses_two_member_union_to_single_type(self) -> None:
        assert strip_none(str | None) is str

    def test_keeps_remaining_members(self) -> None:
        assert strip_none(str | int | None) == str | int


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
    def test_binds_value_by_type(self) -> None:
        scope = InjectionScope(bindings={})
        scope.bind(str, "demovalue")

        assert scope.bindings == {str: "demovalue"}


class TestInvocationContext:
    async def test_resolves_bound_type(self) -> None:
        context = InvocationContext(scope=InjectionScope(bindings={str: "demovalue"}))

        assert await context.resolve(str) == "demovalue"

    async def test_falls_back_to_default(self) -> None:
        context = InvocationContext(scope=InjectionScope(bindings={}))

        assert await context.resolve(str, "fallback") == "fallback"

    async def test_prefers_binding_over_default(self) -> None:
        context = InvocationContext(scope=InjectionScope(bindings={str: "demovalue"}))

        assert await context.resolve(str, "fallback") == "demovalue"

    async def test_raises_without_binding_or_default(self) -> None:
        context = InvocationContext(scope=InjectionScope(bindings={}))

        with pytest.raises(UnresolvedDependencyError):
            await context.resolve(str)


class TestFindBinding:
    def test_returns_binding_from_metadata(self) -> None:
        param = inspect.Parameter("param", inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=_ExampleDep)

        assert find_binding(parse_parameter(param)) == Value("demovalue")

    def test_defaults_to_inject(self) -> None:
        param = inspect.Parameter("param", inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=str)

        assert find_binding(parse_parameter(param)) == Inject()

    def test_skips_plain_metadata(self) -> None:
        annotation = typing.Annotated[str, "note", Value("demovalue")]
        param = inspect.Parameter("param", inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=annotation)

        assert find_binding(parse_parameter(param)) == Value("demovalue")

    def test_ignores_binding_classes(self) -> None:
        param = inspect.Parameter(
            "param", inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=typing.Annotated[str, Value]
        )

        assert find_binding(parse_parameter(param)) == Inject()


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

        context = InvocationContext(scope=InjectionScope(bindings={str: "alex"}))

        assert await invoke(compile_call_plan(fn), context) == "hello alex"

    async def test_invokes_sync_callable(self) -> None:
        def fn(user: Injected[str]) -> str:
            return f"hello {user}"

        context = InvocationContext(scope=InjectionScope(bindings={str: "alex"}))

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


class TestIsAsyncCallable:
    def test_detects_coroutine_function(self) -> None:
        async def fn() -> None:
            pass  # pragma: no cover

        assert is_async_callable(fn) is True

    def test_ignores_plain_function(self) -> None:
        def fn() -> None:
            pass  # pragma: no cover

        assert is_async_callable(fn) is False

    def test_detects_object_with_async_call(self) -> None:
        class Endpoint:
            async def __call__(self) -> None:
                pass  # pragma: no cover

        assert is_async_callable(Endpoint()) is True

    def test_ignores_object_with_sync_call(self) -> None:
        class Endpoint:
            def __call__(self) -> None:
                pass  # pragma: no cover

        assert is_async_callable(Endpoint()) is False


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
    def test_rejects_positional_only_parameter(self) -> None:
        def fn(param: str, /) -> None:
            pass  # pragma: no cover

        with pytest.raises(UnsupportedParameterError) as info:
            compile_call_plan(fn)

        assert "Cannot inject parameter 'param'" in str(info.value)
        assert "test_rejects_positional_only_parameter.<locals>.fn()" in str(info.value)

    def test_rejects_variadic_positional_parameter(self) -> None:
        def fn(*args: str) -> None:
            pass  # pragma: no cover

        with pytest.raises(UnsupportedParameterError) as info:
            compile_call_plan(fn)

        assert "*args can never be filled" in str(info.value)

    def test_rejects_variadic_keyword_parameter(self) -> None:
        def fn(**kwargs: str) -> None:
            pass  # pragma: no cover

        with pytest.raises(UnsupportedParameterError) as info:
            compile_call_plan(fn)

        assert "**kwargs can never be filled" in str(info.value)

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
