import pytest
import wtforms
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from kupala.contrib.forms.fields import Initable
from kupala.contrib.forms.forms import SUBMIT_METHODS, AsyncForm


def sync_validator(form: wtforms.Form, field: wtforms.Field) -> None:
    if field.data == "fail":
        raise wtforms.ValidationError("Error.")


async def async_validator(form: wtforms.Form, field: wtforms.Field) -> None:
    if field.data == "fail":
        raise wtforms.ValidationError("Error.")


@pytest.mark.asyncio
async def test_sync_validation() -> None:
    class Form(AsyncForm):
        name = wtforms.StringField(validators=[sync_validator])

    form = Form(data={"name": "valid"})
    assert await form.validate_async()

    form = Form(data={"name": "fail"})
    assert not await form.validate_async()
    assert form.name.errors == ["Error."]


@pytest.mark.asyncio
async def test_async_validation() -> None:
    class Form(AsyncForm):
        name = wtforms.StringField(validators=[async_validator])

    form = Form(data={"name": "valid"})
    assert await form.validate_async()

    form = Form(data={"name": "fail"})
    assert not await form.validate_async()
    assert form.name.errors == ["Error."]


@pytest.mark.asyncio
async def test_mixed_validation() -> None:
    class Form(AsyncForm):
        name = wtforms.StringField(validators=[async_validator, sync_validator])

    form = Form(data={"name": "valid"})
    assert await form.validate_async()

    form = Form(data={"name": "fail"})
    assert not await form.validate_async()
    assert form.name.errors == ["Error.", "Error."]


@pytest.mark.asyncio
async def test_removes_async_validators_from_field() -> None:
    class Form(AsyncForm):
        name = wtforms.StringField(validators=[async_validator, sync_validator])

    form = Form(data={"name": "valid"})
    assert await form.validate_async()

    form = Form(data={"name": "fail"})
    assert not await form.validate_async()
    assert form.name.errors == ["Error.", "Error."]


@pytest.mark.asyncio
async def test_inline_async_validation() -> None:
    class Form(AsyncForm):
        name = wtforms.StringField()

        async def validate_async_name(self, form: wtforms.Form, field: wtforms.Field) -> None:
            if field.data == "fail":
                raise wtforms.ValidationError("Error.")

    form = Form(data={"name": "valid"})
    assert await form.validate_async()

    form = Form(data={"name": "fail"})
    assert not await form.validate_async()
    assert form.name.errors == ["Error."]


def test_is_submitted() -> None:
    class Form(AsyncForm):
        name = wtforms.StringField()

    form = Form()
    for submit_method in SUBMIT_METHODS:
        assert form.is_submitted(Request({"type": "http", "method": submit_method}))
    assert not form.is_submitted(Request({"type": "http", "method": "GET"}))


@pytest.mark.asyncio
async def test_validate_on_submit() -> None:
    class Form(AsyncForm):
        name = wtforms.StringField(validators=[async_validator])

    form = Form(data={"name": "fail"})
    await form.validate_on_submit(Request({"type": "http", "method": "GET"}))
    assert not form.errors

    await form.validate_on_submit(Request({"type": "http", "method": "POST"}))
    assert form.errors


@pytest.mark.asyncio
async def test_from_request() -> None:
    class Form(AsyncForm):
        name = wtforms.StringField(validators=[async_validator])

    form = await Form.from_request(Request({"type": "http", "method": "GET"}))
    assert form.data == {"name": None}

    async def view(request: Request) -> JSONResponse:
        form = await Form.from_request(request)
        return JSONResponse(dict(form.data))

    app = Starlette(routes=[Route("/", view, methods=["post"])])
    client = TestClient(app)
    assert client.post("/", data={"name": "filled"}).json() == {"name": "filled"}


class _SimpleField(wtforms.StringField, Initable):
    prepared: bool = False

    async def init(self, form: wtforms.Form) -> None:
        self.prepared = True


@pytest.mark.asyncio
async def test_form_prepares_field() -> None:
    class Form(AsyncForm):
        name = _SimpleField()

    form = Form()
    assert not form.name.prepared
    await form.prepare()
    assert form.name.prepared


@pytest.mark.asyncio
async def test_form_prepares_nested_fields() -> None:
    class SubForm(AsyncForm):
        name = _SimpleField()

    class Form(AsyncForm):
        name = wtforms.FieldList(_SimpleField(), min_entries=1)
        subform = wtforms.FormField(SubForm)

    form = Form()
    assert not form.name[0].prepared
    assert not form.subform.form["name"].prepared
    await form.prepare()
    assert form.name[0].prepared
    assert form.subform.form["name"].prepared
