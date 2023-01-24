import typing
import wtforms


class SyncValidator(typing.Protocol):  # pragma: nocover
    def __call__(self, form: wtforms.Form, field: wtforms.Field) -> None:
        ...


class AsyncValidator(typing.Protocol):  # pragma: nocover
    async def __call__(self, form: wtforms.Form, field: wtforms.Field) -> None:
        ...


Validator: typing.TypeAlias = SyncValidator | AsyncValidator
