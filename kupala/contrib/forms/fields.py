import abc
import wtforms


class Preparable:
    @abc.abstractmethod
    async def prepare(self, form: wtforms.Form) -> None:
        ...  # pragma: no cover
