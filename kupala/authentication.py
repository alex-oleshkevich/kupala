from __future__ import annotations

import abc
import typing


class BaseUser(abc.ABC):  # pragma: nocover
    @abc.abstractmethod
    def get_id(self) -> typing.Any:
        raise NotImplementedError()

    @abc.abstractmethod
    def get_display_name(self) -> str:
        raise NotImplementedError()

    @abc.abstractmethod
    def get_scopes(self) -> list[str]:
        raise NotImplementedError()

    @abc.abstractmethod
    def get_hashed_password(self) -> str:
        raise NotImplementedError()
