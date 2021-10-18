import typing as t
from environs import Env
from marshmallow import validate


class DotEnv(Env):
    validators = validate

    def __init__(self, files: t.Iterable[str] = None) -> None:
        super().__init__(expand_vars=True)
        files = files or ['.env', '.env.defaults']
        for file in files:
            self.read_env(file)
