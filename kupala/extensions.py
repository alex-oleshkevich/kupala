from __future__ import annotations

import abc
import typing

from starlette.applications import Starlette
from starlette.requests import Request

T = typing.TypeVar("T")


type ExtensionContext = Starlette | Request
type InstallContext = Starlette


def make_state_key(cls: type[Extension], preferred: str) -> str:
    if preferred:
        return preferred
    return cls.__name__.lower()


class Extension(abc.ABC):
    state_key: str = ""

    def install(self, app: InstallContext) -> None:
        """Install the extension into the application."""
        key = make_state_key(self.__class__, self.state_key)
        setattr(app, key, self)

    @classmethod
    def of(cls, context: ExtensionContext) -> typing.Self:
        return cls._get_state(context, make_state_key(cls, cls.state_key))

    @classmethod
    def _get_state(cls, context: ExtensionContext, attr: str) -> typing.Self:
        try:
            match context:
                case Starlette():
                    return typing.cast(typing.Self, getattr(context.state, attr))
                case Request():
                    return typing.cast(typing.Self, getattr(context.app, attr))
            raise ValueError("Unknown context type.")
        except AttributeError:
            raise ValueError("Extension {name} not installed.".format(name=cls.__name__))
