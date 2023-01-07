import typing
import wtforms


class SyncValidator(typing.Protocol):
    def __call__(self, form: wtforms.Form, field: wtforms.Field) -> None:
        ...


class AsyncValidator(typing.Protocol):
    async def __call__(self, form: wtforms.Form, field: wtforms.Field) -> None:
        ...


Validator: typing.TypeAlias = SyncValidator | AsyncValidator
