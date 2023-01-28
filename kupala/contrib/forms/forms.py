import anyio
import inspect
import typing
import wtforms
from starlette.datastructures import ImmutableMultiDict
from starlette.requests import Request

from kupala.contrib.forms.fields import Initable, NeedsFinalization
from kupala.contrib.forms.validators import AsyncValidator

_F = typing.TypeVar("_F", bound="AsyncForm")
SUBMIT_METHODS = ["POST", "PUT", "PATCH", "DELETE"]


async def _perform_async_validation(
    results: list[bool], form: wtforms.Form, field: wtforms.Field, validator: AsyncValidator
) -> None:
    try:
        await validator(form, field)
    except wtforms.ValidationError as ex:
        results.append(False)
        field.errors.append(ex.args[0])
    else:
        results.append(True)


def iterate_form_fields(form: typing.Iterable[wtforms.Field]) -> typing.Generator[wtforms.Field, None, None]:
    for field in form:
        if isinstance(field, (wtforms.FieldList, wtforms.FormField)):
            yield from iterate_form_fields(field)
        else:
            yield field


class AsyncForm(wtforms.Form):
    _fields: dict[str, wtforms.Field]

    def __init__(
        self,
        formdata: ImmutableMultiDict | None = None,
        obj: typing.Any | None = None,
        data: typing.Any | None = None,
        context: typing.Mapping[str, typing.Any] | None = None,
        **kwargs: typing.Any,
    ):
        super().__init__(formdata=formdata, obj=obj, data=data, **kwargs)
        self.context = context or {}

    def is_submitted(self, request: Request) -> bool:
        return request.method in SUBMIT_METHODS

    async def validate_on_submit(self, request: Request) -> bool:
        return self.is_submitted(request) and await self.validate_async()

    async def validate_async(self) -> bool:
        async_validators: dict[wtforms.Field, list[AsyncValidator]] = {}

        for field_name, field in self._fields.items():
            async_validators.setdefault(field, [])
            async_validators[field] = [
                validator for validator in field.validators if inspect.iscoroutinefunction(validator)
            ]
            field.validators = [validator for validator in field.validators if validator not in async_validators[field]]
            if inline_validator := getattr(self, f"validate_async_{field_name}", None):
                async_validators[field].append(inline_validator)

        sync_valid = super().validate()
        completed: list[bool] = [sync_valid]
        async with anyio.create_task_group() as tg:
            for field, validators in async_validators.items():
                for validator in validators:
                    tg.start_soon(_perform_async_validation, completed, self, field, validator)

        return False not in completed

    async def prepare(self) -> None:
        for field in iterate_form_fields(self):
            if isinstance(field, Initable):
                await field.init(self)

    async def populate_obj(self, obj: typing.Any) -> None:
        for field in iterate_form_fields(self):
            if isinstance(field, NeedsFinalization):
                field.data = await field.finalize()

        super().populate_obj(obj)

    @classmethod
    async def from_request(
        cls: type[_F],
        request: Request,
        obj: typing.Any | None = None,
        prefix: str = "",
        data: typing.Mapping[str, typing.Any] | None = None,
        meta: typing.Mapping[str, typing.Any] | None = None,
        context: typing.Mapping[str, typing.Any] | None = None,
        extra_filters: typing.Mapping[str, typing.Any] | None = None,
    ) -> _F:
        form_data = None
        if request.method in SUBMIT_METHODS:
            form_data = await request.form()

        form: AsyncForm = cls(
            request=request,
            formdata=form_data,
            obj=obj,
            prefix=prefix,
            data=data,
            meta=meta,
            context=context,
            extra_filters=extra_filters,
        )
        await form.prepare()
        return form
