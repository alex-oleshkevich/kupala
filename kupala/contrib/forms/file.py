import anyio
import os
import typing
import wtforms
from starlette.datastructures import UploadFile

from kupala.contrib.forms import Validator
from kupala.contrib.forms.fields import NeedsFinalization
from kupala.storages import UploadFilename, generate_file_name


class FileUploader(typing.Protocol):  # pragma: no cover
    async def __call__(self, upload: UploadFile) -> typing.Any:
        ...


class SimpleUploader:
    def __init__(self, destination: str | os.PathLike | UploadFilename) -> None:
        self.destination = destination

    async def __call__(self, upload: UploadFile) -> str:
        path = generate_file_name(upload, self.destination)
        async with await anyio.open_file(path, "wb") as f:
            while chunk := await upload.read(1024 * 64):
                await f.write(chunk)
        return path


class AsyncFileField(wtforms.FileField, NeedsFinalization):
    data: UploadFile | str | None

    def __init__(
        self,
        uploader: FileUploader,
        label: str | None = None,
        validators: typing.Sequence[Validator] | None = None,
        **kwargs: typing.Any,
    ):
        super().__init__(label, validators, **kwargs)
        self.uploader = uploader
        self._original_data: str | None = None

    @property
    def file_uploaded(self) -> bool:
        if isinstance(self.data, UploadFile) and self.data.filename:
            return True
        return False

    async def upload(self) -> str:
        assert isinstance(self.data, UploadFile)
        return await self.uploader(self.data)

    async def finalize(self) -> typing.Any:
        if self.file_uploaded:
            return await self.upload()
        return self._original_data

    def process_formdata(self, valuelist: typing.Sequence[UploadFile]) -> None:
        assert not isinstance(self.data, UploadFile)
        self._original_data = self.data
        super().process_formdata(valuelist)
