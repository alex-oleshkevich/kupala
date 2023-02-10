import datetime
import os
import random
import string
import time
import typing
from starlette.datastructures import UploadFile

UploadFilename = typing.Callable[[UploadFile], str]


def generate_file_name(
    upload_file: UploadFile,
    destination: str | UploadFilename | os.PathLike,
    extra_tokens: dict["str", typing.Any] | None = None,
) -> str:
    """
    Generate a file path for an upload.

    Example:
    ```python
    destination = generate_file_name(uploaded_file, '/uploads/{date}/{prefix}_{file_name}')
    ```

    :param upload_file: Uploaded file
    :param destination: A destination path. May be callable.
    :param extra_tokens: Additional formatting tokens.
    """
    filename = upload_file.filename if upload_file.filename else "file.bin"
    prefix = "".join(random.choices(string.ascii_lowercase, k=6))
    file_name, ext = os.path.splitext(filename)
    timestamp = int(time.time())
    current_date = datetime.datetime.now().date().isoformat()
    current_time = datetime.datetime.now().time().isoformat()
    ext = ext[1:]
    extra_tokens = extra_tokens or {}

    format_tokens = {
        "prefix": prefix,
        "name": file_name,
        "ext": ext,
        "date": current_date,
        "time": current_time,
        "timestamp": timestamp,
        "file_name": upload_file.filename,
        **extra_tokens,
    }
    destination = destination(upload_file) if callable(destination) else str(destination)
    return destination.format(**format_tokens)
