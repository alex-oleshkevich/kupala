import abc
import typing
import wtforms


class Initable(abc.ABC):  # pragma: no cover
    @abc.abstractmethod
    async def init(self, form: wtforms.Form) -> None:
        ...


class NeedsFinalization(abc.ABC):  # pragma: no cover
    data: typing.Any  # mypy only

    @abc.abstractmethod
    async def finalize(self) -> typing.Any:
        ...
