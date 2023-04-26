import abc
import typing
from starlette.applications import AppType


class Extension:  # pragma: nocover
    @abc.abstractmethod
    def bootstrap(self, app: AppType) -> typing.AsyncContextManager[typing.Mapping[str, typing.Any] | None]:
        ...
