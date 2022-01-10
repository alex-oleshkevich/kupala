import os
import pathlib
import pytest

from kupala.utils import camel_to_snake, import_string, resolve_path, run_async


def test_resolve_path(tmp_path: pathlib.Path) -> None:
    assert os.path.dirname(os.__file__) in resolve_path('@os')
    assert 'kupala/requests' in resolve_path('@kupala/requests')
    assert 'kupala/templates/errors/http_error.html' in resolve_path('@kupala/templates/errors/http_error.html')
    assert __file__ in resolve_path(__file__)

    assert str(tmp_path) in resolve_path(tmp_path)


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
