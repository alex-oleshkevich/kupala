import abc
import wtforms


class Initable:  # pragma: no cover
    @abc.abstractmethod
    async def init(self, form: wtforms.Form) -> None:
        ...
