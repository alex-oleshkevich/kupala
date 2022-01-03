from __future__ import annotations

import functools
import pytest
import typing as t

from kupala.container import Container, InjectionError, get_callable_types


class SomeClass:
    def __init__(self, a: str) -> None:
        pass


class JustClass:
    def instance_method(self, a: str, b: int) -> None:
        pass

    @classmethod
    def class_method(cls, a: str, b: int) -> None:
        pass

    @staticmethod
    def static_method(a: str, b: int) -> None:
        pass


def example_callable(a: str, /, b: SomeClass, *, c: int = 42, d=False) -> None:  # type: ignore
    pass


def test_extracts_arguments_from_function() -> None:
    args = get_callable_types(example_callable)

    assert args.return_type is type(None)  # noqa

    assert 'a' in args
    assert args['a'].is_annotated
    assert args['a'].annotation == str
    assert not args['a'].has_default
    assert args['a'].is_positional_only
    assert not args['a'].is_keyword

    assert 'b' in args
    assert args['b'].annotation == SomeClass
    assert not args['b'].has_default
    assert not args['b'].is_positional_only
    assert args['b'].is_keyword

    assert 'c' in args
    assert args['c'].annotation == int
    assert args['c'].has_default
    assert args['c'].default == 42
    assert not args['c'].is_positional_only
    assert args['c'].is_keyword

    assert 'd' in args
    assert not args['d'].is_annotated


def test_extracts_arguments_from_class_constructor() -> None:
    args = get_callable_types(SomeClass)
    assert len(args) == 1
    assert 'a' in args


class SomeClassChild(SomeClass):
    def __init__(self, b: int, *args: t.Any, **kwargs: t.Any) -> None:
        super().__init__(*args, **kwargs)


class SomeClassChildOfChild(SomeClassChild):
    def __init__(self, c: int, *args: t.Any, **kwargs: t.Any) -> None:
        super().__init__(*args, **kwargs)


def test_extracts_arguments_from_class_stack() -> None:
    args = get_callable_types(SomeClassChildOfChild)
    assert len(args) == 3
    assert 'a' in args
    assert 'b' in args
    assert 'c' in args


def test_extracts_arguments_from_class_without_args() -> None:
    class PureClass:
        ...

    args = get_callable_types(PureClass)
    assert not args.is_return_type_annotated
    assert len(args) == 0


def test_extracts_arguments_from_instance_method() -> None:
    instance = JustClass()

    args = get_callable_types(instance.instance_method)
    assert len(args) == 2


def test_extracts_arguments_from_class_method() -> None:
    args = get_callable_types(JustClass.class_method)
    assert len(args) == 2


def test_extracts_arguments_from_static_method() -> None:
    args = get_callable_types(JustClass.static_method)
    assert len(args) == 2


class ClassToInject:
    ...


def test_invokes_callable() -> None:
    service_instance = ClassToInject()
    container = Container()
    container.bind(ClassToInject, service_instance)

    def some_callable(some_class: ClassToInject) -> ClassToInject:
        return some_class

    assert container.invoke(some_callable) == service_instance


@pytest.mark.asyncio
async def test_invokes_async_callable() -> None:
    service_instance = ClassToInject()
    container = Container()
    container.bind(ClassToInject, service_instance)

    async def some_callable(some_class: ClassToInject) -> ClassToInject:
        return some_class

    instance = await container.invoke(some_callable)
    assert instance == service_instance


def test_positional_only_not_supported() -> None:
    service_instance = ClassToInject()
    container = Container()
    container.bind(ClassToInject, service_instance)

    def some_callable(some_class: ClassToInject, /) -> ClassToInject:
        return some_class

    with pytest.raises(InjectionError) as ex:
        container.invoke(some_callable)
        assert ex.value.error_type == InjectionError.ErrorType.POSITIONAL_ONLY_ERROR


def test_argument_not_annotated() -> None:
    container = Container()

    def some_callable(some_class) -> ClassToInject:  # type: ignore
        return some_class

    with pytest.raises(InjectionError) as ex:
        container.invoke(some_callable)
        assert ex.value.error_type == InjectionError.ErrorType.NOT_ANNOTATED_ERROR


def test_passes_extra_arguments() -> None:
    service_instance = ClassToInject()
    container = Container()
    container.bind(ClassToInject, service_instance)

    def some_callable(some_class: ClassToInject, a: str, b: int) -> t.Tuple[ClassToInject, str, int]:
        return some_class, a, b

    assert container.invoke(some_callable, extra_kwargs={'a': 'a', 'b': 'b'}) == (service_instance, 'a', 'b')


def test_service_not_registered() -> None:
    container = Container()

    def some_callable(some_class: ClassToInject, a: str, b: int) -> t.Tuple[ClassToInject, str, int]:
        return some_class, a, b

    with pytest.raises(InjectionError) as ex:
        assert container.invoke(some_callable)
        assert ex.value.error_type == InjectionError.ErrorType.SERVICE_NOT_FOUND


def test_ignores_unknown_extra_arguments() -> None:
    service_instance = ClassToInject()
    container = Container()
    container.bind(ClassToInject, service_instance)

    def some_callable(some_class: ClassToInject, a: str, b: int) -> t.Tuple[ClassToInject, str, int]:
        return some_class, a, b

    assert container.invoke(some_callable, extra_kwargs={'a': 'a', 'b': 'b', 'c': 'c'}) == (service_instance, 'a', 'b')


class ClassToInvoke:
    def __init__(self, a: ClassToInject) -> None:
        self.a = a


def test_invokes_class() -> None:
    service_instance = ClassToInject()
    container = Container()
    container.bind(ClassToInject, service_instance)

    instance = container.invoke(ClassToInvoke)
    assert isinstance(instance, ClassToInvoke)
    assert instance.a == service_instance


def test_invokes_partial() -> None:
    def fn(a: ClassToInject, b: str) -> t.Tuple[ClassToInject, str]:
        return a, b

    container = Container()
    service_instance = ClassToInject()
    container.bind(ClassToInject, service_instance)

    partial = functools.partial(fn, b='b')
    assert container.invoke(partial) == (service_instance, 'b')
