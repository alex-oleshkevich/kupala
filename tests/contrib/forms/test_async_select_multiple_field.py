import pytest
import wtforms
from starlette.requests import Request
from wtforms.fields.core import UnboundField

from kupala.contrib.forms.choices import AsyncSelectMultipleField, FormChoices
from kupala.contrib.forms.forms import AsyncForm


@pytest.mark.asyncio
async def test_simple_choices() -> None:
    form = AsyncForm(context={"request": Request})
    unbound_field: UnboundField = AsyncSelectMultipleField(choices=[("1", "One")])
    field: AsyncSelectMultipleField = unbound_field.bind(form, "name")
    await field.init(form)
    assert field.choices == [("1", "One")]


@pytest.mark.asyncio
async def test_sync_callback() -> None:
    def choices() -> FormChoices:
        return [("1", "One")]

    form = AsyncForm(context={"request": Request})
    unbound_field: UnboundField = AsyncSelectMultipleField(choices=choices)
    field: AsyncSelectMultipleField = unbound_field.bind(form, "name")
    await field.init(form)
    assert field.choices == [("1", "One")]


@pytest.mark.asyncio
async def test_async_callback() -> None:
    async def choices(form: wtforms.Form) -> FormChoices:
        return [("1", "One")]

    form = AsyncForm(context={"request": Request})
    unbound_field: UnboundField = AsyncSelectMultipleField(choices=choices)
    field: AsyncSelectMultipleField = unbound_field.bind(form, "name")
    await field.init(form)
    assert field.choices == [("1", "One")]
