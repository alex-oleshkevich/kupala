import os
import pytest
import typing

from kupala.utils import camel_to_snake, import_string, run_async, to_string_list


def test_import_string() -> None:
    module = import_string('os:path')
    assert module == os.path

    module = import_string('os.path')
    assert module == os.path


def test_camel_to_snake() -> None:
    assert camel_to_snake('CamelToSnake') == 'camel_to_snake'


@pytest.mark.asyncio
async def test_run_async() -> None:
    def plain(arg: str, *, kwarg: str) -> str:
        return f'called {arg} {kwarg}'

    async def coro(arg: str, *, kwarg: str) -> str:
        return f'called {arg} {kwarg}'

    assert await run_async(plain, 'one', kwarg='two') == 'called one two'
    assert await run_async(coro, 'one', kwarg='two') == 'called one two'


def test_to_string_list() -> None:
    assert to_string_list(None) == []
    assert to_string_list('test') == ['test']
    assert to_string_list(['test']) == ['test']

    def gen() -> typing.Generator[str, None, None]:
        yield 'test'

    assert to_string_list(gen()) == ['test']
