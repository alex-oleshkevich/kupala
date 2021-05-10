from unittest import mock

import pytest

from kupala.container import Container
from kupala.container import NoTypeHintError
from kupala.container import ParameterUnsupported
from kupala.container import service
from kupala.container import ServiceNotFound
from kupala.container import tag


class _Stub1:
    ...


@pytest.fixture
def container():
    return Container()


def test_resolve(container):
    container.bind("a", 1)
    container.alias("a", "b")
    container.alias("b", "c")

    assert container.resolve("a") == "a"
    assert container.resolve("b") == "a"
    assert container.resolve("c") == "a"

    with pytest.raises(ServiceNotFound):
        assert container.resolve("unknown") == "unknown"


def test_bind_has_get(container):
    container.bind("a", 1)
    assert "a" in container
    assert container.get("a") == 1
    assert container["a"] == 1

    container["b"] = "b"
    assert container["b"] == "b"
    del container["b"]
    assert "b" not in container


def test_factory(container):
    def factory() -> _Stub1:
        return _Stub1()

    container.factory(_Stub1, factory)
    instance = container.get(_Stub1)
    assert isinstance(instance, _Stub1)


def test_factory_singleton(container):
    def factory() -> _Stub1:
        return _Stub1()

    container.factory(_Stub1, factory, singleton=True)
    instance = container.get(_Stub1)
    assert container.get(_Stub1) == instance
    assert container.get(_Stub1) == instance


class _Stub2:
    ...


class _Stub3:
    def __init__(self, stub: _Stub1, stub2: _Stub2):
        self.stub = stub
        self.stub2 = stub2


def test_factory_injects(container):
    def factory(stub: _Stub1, stub2: _Stub2) -> _Stub3:
        return _Stub3(stub, stub2)

    stub1 = _Stub1()
    stub2 = _Stub2()
    container.bind(_Stub1, stub1)
    container.bind(_Stub2, stub2)
    container.factory(_Stub3, factory)
    instance = container.get(_Stub3)
    assert isinstance(instance, _Stub3)
    assert instance.stub == stub1
    assert instance.stub2 == stub2


def test_invoke(container):
    container.bind(_Stub1, "stub1")
    container.bind(_Stub2, "stub2")

    def fn(s1: _Stub1, s2: _Stub2):
        return [s1, s2]

    assert container.invoke(fn) == ["stub1", "stub2"]


def test_invoke_with_positional(container):
    def fn(s1: _Stub1, /):
        pass

    with pytest.raises(ParameterUnsupported):
        container.invoke(fn)


def test_invoke_with_missing_type_hints(container):
    def fn(s1):
        pass

    with pytest.raises(NoTypeHintError):
        container.invoke(fn)


def test_invoke_with_hints(container):
    container.bind(_Stub1, "stub1")

    def fn(s1: _Stub1, s2: _Stub2):
        return [s1, s2]

    assert container.invoke(fn, s2="stub2") == ["stub1", "stub2"]


def test_invoke_creates_class_instance(container):
    class _Dep:
        def __init__(self, stub: _Stub1):
            self.stub = stub

    container.bind(_Stub1, "stub")
    instance = container.invoke(_Dep)
    assert instance.stub == "stub"


@pytest.mark.asyncio
async def test_invokes_async_function(container):
    async def fn(stub: _Stub1):
        return stub

    container.bind(_Stub1, _Stub1())
    result = await container.invoke(fn)
    assert result == container.get(_Stub1)


def test_tag(container):
    # service with one tag
    container.bind("a", 1, tags="service.a")
    assert container.get_by_tag("service.a") == [1]

    # service with multiple tags
    container.bind("b", 2, tags=["service.b", "service.b1"])
    assert container.get_by_tag("service.b") == [2]
    assert container.get_by_tag("service.b1") == [2]

    # tag a service
    container.tag("a", "service.c")
    assert container.get_by_tag("service.c") == [1]

    # tag a service with multiple tags
    container.tag("a", ["service.d", "service.d1"])
    assert container.get_by_tag("service.d") == [1]
    assert container.get_by_tag("service.d1") == [1]

    container.bind("d", 4, tags=["d1", "d2"])
    assert container.get_tags("d") == ["d1", "d2"]


def test_alias(container):
    container.bind("a", 1, aliases="a1")
    assert "a1" in container
    assert container.get("a1") == 1

    container.bind("b", 1, aliases=["b1", "b2"])
    assert container.get("b1") == 1
    assert container.get("b2") == 1

    container.alias("a", "c")
    assert container.get("c") == 1

    container.bind("d", 4, aliases=["d1", "d2"])
    container.alias("d2", "d3")
    assert container.get_aliases("d") == ["d1", "d2", "d3"]


def test_remove(container):
    container.bind("a", 1, aliases=["a1", "a2"], tags=["ta1", "ta2"])
    container.alias("a2", "b")

    container.remove("a")
    with pytest.raises(ServiceNotFound):
        container.get("a1")
    with pytest.raises(ServiceNotFound):
        container.get("a2")

    assert "a" not in container
    assert "ta1" not in container.tags
    assert "ta2" not in container.tags
    assert "a1" not in container.aliases
    assert "a2" not in container.aliases

    # test __delitem__
    container.bind("a", 1)
    del container["a"]
    assert "a" not in container


def test_post_create_hooks(container):
    def factory():
        return 1

    fn = mock.MagicMock()
    fn2 = mock.MagicMock()
    container.factory("f", factory).after_created(fn)
    container.add_post_create_hook("f", fn2)
    container.get("f")
    fn.assert_called_once_with(1)
    fn2.assert_called_once_with(1)


def test_post_create_hook_called_once_for_singleton(container):
    cb = mock.MagicMock()
    container.singleton('service', lambda: True).after_created(cb)
    container.get('service')
    container.get('service')

    cb.assert_called_once()


def test_post_create_hook_called_many_times_for_factory(container):
    cb = mock.MagicMock()
    container.factory('service', lambda: True).after_created(cb)
    container.get('service')
    container.get('service')

    assert cb.call_count == 2


def test_fluent_interface(container):
    def hook():
        ...

    container.bind("a", 1).tag("t1").alias("a1").after_created(hook)
    assert "t1" in container.tags
    assert "a1" in container.aliases


def test_injects_alias(container):
    def fn(stub: service("stub1")):
        return stub

    instance = _Stub1()
    container.bind(_Stub1, instance, aliases="stub1")
    assert container.invoke(fn) == instance


def test_injects_by_tag(container):
    def fn(stub: tag("stub1")):
        return stub

    instance = _Stub1()
    container.bind(_Stub1, instance, tags="stub1")
    assert container.invoke(fn) == [instance]
