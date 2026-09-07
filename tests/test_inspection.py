import contextlib
import typing

from kupala.inspection import (
    callable_name,
    is_async_callable,
    is_async_generator_callable,
    is_generator_callable,
    is_optional,
    strip_none,
    type_name,
    unwrap_alias,
    unwrap_annotation,
)

type _TaggedStr = typing.Annotated[str, "tag"]
type _AliasOfAlias = _TaggedStr
type _MaybeStr = str | None
type _Tagged[T] = typing.Annotated[T, "outer"]
type _NestedTag = _Tagged[_TaggedStr]


class TestCallableName:
    def test_renders_module_and_qualname(self) -> None:
        def fn() -> None:
            pass  # pragma: no cover

        assert (
            callable_name(fn) == "tests.test_inspection.TestCallableName.test_renders_module_and_qualname.<locals>.fn"
        )

    def test_falls_back_to_the_class_of_a_callable_object(self) -> None:
        class Endpoint:
            def __call__(self) -> None:
                pass  # pragma: no cover

        assert callable_name(Endpoint()).endswith("Endpoint")


class TestTypeName:
    def test_renders_a_type_by_qualname(self) -> None:
        assert type_name(str) == "str"

    def test_names_a_union_by_its_qualname(self) -> None:
        assert type_name(str | None) == "Union"

    def test_falls_back_to_repr(self) -> None:
        # a plain value has no `__qualname__` to borrow
        assert type_name(42) == "42"


class TestUnwrapAlias:
    def test_returns_plain_type_unchanged(self) -> None:
        assert unwrap_alias(str) is str

    def test_resolves_bare_alias(self) -> None:
        assert unwrap_alias(_TaggedStr) == typing.Annotated[str, "tag"]

    def test_resolves_chained_alias(self) -> None:
        assert unwrap_alias(_AliasOfAlias) == typing.Annotated[str, "tag"]

    def test_resolves_subscripted_alias(self) -> None:
        assert unwrap_alias(_Tagged[str]) == typing.Annotated[str, "outer"]

    def test_resolves_union_alias(self) -> None:
        assert unwrap_alias(_MaybeStr) == str | None


class TestUnwrapAnnotation:
    def test_plain_type_carries_no_metadata(self) -> None:
        assert unwrap_annotation(str) == (str, ())

    def test_extracts_metadata_from_alias(self) -> None:
        assert unwrap_annotation(_TaggedStr) == (str, ("tag",))

    def test_extracts_metadata_from_subscripted_alias(self) -> None:
        assert unwrap_annotation(_Tagged[str]) == (str, ("outer",))

    def test_merges_nested_metadata_innermost_first(self) -> None:
        assert unwrap_annotation(_NestedTag) == (str, ("tag", "outer"))

    def test_keeps_every_metadata_entry(self) -> None:
        assert unwrap_annotation(typing.Annotated[str, "first", "second"]) == (str, ("first", "second"))

    def test_keeps_optional_union_intact(self) -> None:
        assert unwrap_annotation(typing.Annotated[str | None, "tag"]) == (str | None, ("tag",))


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


class TestIsGeneratorCallable:
    def test_detects_generator_function(self) -> None:
        def fn() -> typing.Iterator[str]:
            yield "demovalue"  # pragma: no cover

        assert is_generator_callable(fn) is True

    def test_ignores_plain_function(self) -> None:
        def fn() -> str:
            return "demovalue"  # pragma: no cover

        assert is_generator_callable(fn) is False

    def test_ignores_async_generator_function(self) -> None:
        async def fn() -> typing.AsyncIterator[str]:
            yield "demovalue"  # pragma: no cover

        assert is_generator_callable(fn) is False

    def test_detects_object_with_generator_call(self) -> None:
        class Maker:
            def __call__(self) -> typing.Iterator[str]:
                yield "demovalue"  # pragma: no cover

        assert is_generator_callable(Maker()) is True

    def test_ignores_contextmanager_decorated_function(self) -> None:
        # the decorator hides the generator, so callers must not try to enter what it returns
        @contextlib.contextmanager
        def fn() -> typing.Iterator[str]:
            yield "demovalue"  # pragma: no cover

        assert is_generator_callable(fn) is False


class TestIsAsyncGeneratorCallable:
    def test_detects_async_generator_function(self) -> None:
        async def fn() -> typing.AsyncIterator[str]:
            yield "demovalue"  # pragma: no cover

        assert is_async_generator_callable(fn) is True

    def test_ignores_coroutine_function(self) -> None:
        async def fn() -> str:
            return "demovalue"  # pragma: no cover

        assert is_async_generator_callable(fn) is False

    def test_ignores_generator_function(self) -> None:
        def fn() -> typing.Iterator[str]:
            yield "demovalue"  # pragma: no cover

        assert is_async_generator_callable(fn) is False

    def test_detects_object_with_async_generator_call(self) -> None:
        class Maker:
            async def __call__(self) -> typing.AsyncIterator[str]:
                yield "demovalue"  # pragma: no cover

        assert is_async_generator_callable(Maker()) is True

    def test_ignores_asynccontextmanager_decorated_function(self) -> None:
        @contextlib.asynccontextmanager
        async def fn() -> typing.AsyncIterator[str]:
            yield "demovalue"  # pragma: no cover

        assert is_async_generator_callable(fn) is False
