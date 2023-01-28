import dataclasses

import io
import pathlib
import pytest
import wtforms
from starlette.datastructures import FormData, UploadFile

from kupala.contrib.forms import AsyncForm
from kupala.contrib.forms.file import AsyncFileField, SimpleUploader


@pytest.mark.asyncio
async def test_simple_uploader(tmp_path: pathlib.Path) -> None:
    destination = tmp_path / "upload.bin"
    uploader = SimpleUploader(destination)
    upload_file = UploadFile(filename="file.txt", file=io.BytesIO(b"CONTENT"))
    path = await uploader(upload_file)
    assert path == str(destination)
    assert destination.read_text() == "CONTENT"


@pytest.mark.asyncio
async def test_async_file_uploads(tmp_path: pathlib.Path) -> None:
    destination = tmp_path / "upload.bin"
    uploader = SimpleUploader(destination)
    field = AsyncFileField(name="file", uploader=uploader, _form=wtforms.Form(prefix=""))
    field.data = UploadFile(filename="file.txt", file=io.BytesIO(b"CONTENT"))
    assert await field.upload() == str(destination)
    assert destination.read_text() == "CONTENT"


@pytest.mark.asyncio
async def test_async_file_finalizable(tmp_path: pathlib.Path) -> None:
    destination = tmp_path / "upload.bin"
    uploader = SimpleUploader(destination)
    field = AsyncFileField(name="file", uploader=uploader, _form=wtforms.Form(prefix=""))
    field.data = UploadFile(filename="file.txt", file=io.BytesIO(b"CONTENT"))
    assert await field.finalize() == str(destination)


@pytest.mark.asyncio
async def test_async_file_processes_uploaded_files(tmp_path: pathlib.Path) -> None:
    destination = tmp_path / "upload.bin"
    uploader = SimpleUploader(destination)

    class MyForm(AsyncForm):
        file = AsyncFileField(uploader=uploader)

    @dataclasses.dataclass
    class Model:
        file: str

    model = Model(file="original")
    form = MyForm(obj=model, formdata=FormData({"file": UploadFile(filename="file.txt", file=io.BytesIO(b"CONTENT"))}))
    await form.populate_obj(model)
    assert model.file == str(destination)
    assert destination.read_text() == "CONTENT"


@pytest.mark.asyncio
async def test_async_file_ignores_not_uploaded_files(tmp_path: pathlib.Path) -> None:
    destination = tmp_path / "upload.bin"
    uploader = SimpleUploader(destination)

    class MyForm(AsyncForm):
        file = AsyncFileField(uploader=uploader)

    @dataclasses.dataclass
    class Model:
        file: str

    model = Model(file="original")
    form = MyForm(obj=model, formdata=FormData({"file": UploadFile(filename="", file=io.BytesIO(b""))}))
    await form.populate_obj(model)

    assert model.file == "original"
