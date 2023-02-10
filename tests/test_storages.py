import io
from starlette.datastructures import UploadFile

from kupala.storages import generate_file_name


def test_generate_file_name() -> None:
    upload = UploadFile(io.BytesIO(b""), filename="sample.txt")
    assert generate_file_name(upload, "/uploads/{name}.{ext}") == "/uploads/sample.txt"


def test_generate_file_name_with_custom_tokens() -> None:
    upload = UploadFile(io.BytesIO(b""), filename="sample.txt")
    assert generate_file_name(upload, "/uploads/{pk}/{name}.{ext}", extra_tokens={"pk": 1}) == "/uploads/1/sample.txt"


def test_generate_file_name_with_callable_destination() -> None:
    upload = UploadFile(io.BytesIO(b""), filename="sample.txt")

    def destination(file: UploadFile) -> str:
        return "/uploads/{name}.{ext}"

    assert generate_file_name(upload, destination) == "/uploads/sample.txt"
