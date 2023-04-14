import abc
import typing
from starlette.applications import AppType


class Extension:
    @abc.abstractmethod
    def bootstrap(self, app: AppType) -> typing.AsyncContextManager[typing.Mapping[str, typing.Any] | None]:
        ...
