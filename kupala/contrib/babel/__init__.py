import contextlib
import os
import starlette_babel
import typing
from starlette.applications import AppType
from starlette.requests import Request
from starlette_babel import get_translator

from kupala.extensions import Extension


def _translator_injection(request: Request) -> starlette_babel.Translator:
    return request.state.translator


Translator = typing.Annotated[starlette_babel.Translator, _translator_injection]


class BabelExtension(Extension):
    def __init__(self, translation_dirs: list[str | os.PathLike[str]]) -> None:
        self.translation_dirs = translation_dirs

    @contextlib.asynccontextmanager
    async def bootstrap(self, app: AppType) -> typing.AsyncIterator[typing.Mapping[str, typing.Any]]:
        translator = get_translator()
        translator.load_from_directories(self.translation_dirs)
        yield {"translator": translator}
