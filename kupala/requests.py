from __future__ import annotations

import anyio
import mimetypes
import os
import pathlib
import re
import typing
import typing as t
import uuid
from imia import UserToken
from starlette import datastructures as ds, requests
from starlette.requests import empty_receive, empty_send
from starlette.types import Receive, Scope, Send
from starsessions import Session

if t.TYPE_CHECKING:
    from .application import Kupala


class OldFormInput(t.Mapping):
    def __init__(self, data: dict) -> None:
        self._data = data

    def get(self, key: str, default: t.Any = None) -> t.Any:
        return self._data.get(key, default)

    def __getitem__(self, item: str) -> t.Any:
        return self._data[item]

    def __len__(self) -> int:
        return len(self._data)

    def __iter__(self) -> t.Iterator[t.Tuple[str, t.Any]]:
        return iter(self._data)

    def __contains__(self, item: object) -> bool:
        return item in self._data

    def to_json(self) -> dict:
        return self._data


class FormErrors:
    def __init__(self, error_message: str, errors: t.Mapping) -> None:
        self.message = error_message
        self.field_errors = errors

    def to_json(self) -> dict:
        return {
            'message': self.message,
            'field_errors': self.field_errors,
        }

    def __bool__(self) -> bool:
        return bool(self.field_errors or self.message)


class QueryParams(requests.QueryParams):
    def get_bool(self, key: str, default: bool = None) -> t.Optional[bool]:
        value = self.get(key, None)
        return value.lower() in ['t', 'true', 'yes', 'on', '1'] if value is not None else default

    def get_list(self, key: str, subcast: t.Callable = None) -> list[str]:
        items = self.getlist(key)
        if subcast:
            return list(map(subcast, items))
        return items

    def get_int(self, key: str, default: int = None) -> t.Optional[int]:
        value: str = self.get(key, None)
        return int(value) if value is not None and value.isnumeric() else default


class FormData(requests.FormData):
    pass


class UploadFile(ds.UploadFile):
    def __init__(self, filename: str, file: typing.IO = None, content_type: str = "") -> None:
        super().__init__(filename, file, content_type)

    @classmethod
    def from_base_upload_file(cls, upload_file: ds.UploadFile) -> UploadFile:
        return UploadFile(filename=upload_file.filename, file=upload_file.file, content_type=upload_file.content_type)

    async def save(self, directory: t.Union[str, os.PathLike], filename: str = None) -> str:
        uploaded_filename = self.filename
        prefix = str(uuid.uuid4().fields[-1])[:5]
        extension = pathlib.Path(uploaded_filename).suffix
        if not extension:
            extension = mimetypes.guess_extension(self.content_type) or 'bin'
        suggested_filename = f'{prefix}_{uploaded_filename}.{extension}'

        file_path = os.path.join(directory, filename or suggested_filename)
        async with await anyio.open_file(file_path, mode='wb') as f:
            await f.write(await self.read())
        return file_path

    async def read(self, size: int = -1) -> bytes:
        return t.cast(bytes, await super().read(size))

    async def read_string(self, size: int = -1, encoding: str = 'utf8', errors: str = 'strict') -> str:
        return (await self.read(size)).decode(encoding, errors)


class FilesData:
    def __init__(self, files: FormData) -> None:
        self._files = files

    def get(self, key: str, default: t.Any = None) -> t.Optional[UploadFile]:
        return self._files.get(key, default)

    def getlist(self, key: str) -> list[UploadFile]:
        return t.cast(list[UploadFile], self._files.getlist(key))


class Request(requests.Request):
    def __new__(cls, scope: Scope, receive: Receive = empty_receive, send: Send = empty_send) -> Request:
        if 'request' not in scope:
            instance = super().__new__(cls)
            instance.__init__(scope, receive, send)
            scope['request'] = instance
        return scope['request']

    @property
    def query_params(self) -> QueryParams:
        return QueryParams(super().query_params)

    @property
    def app(self) -> 'Kupala':
        return self.scope['app']

    @property
    def auth(self) -> UserToken:
        assert "auth" in self.scope, "AuthenticationMiddleware must be installed to access request.auth"
        return self.scope["auth"]

    @property
    def wants_json(self) -> bool:
        """Test if request sends Accept header
        with 'application/json' value."""
        return "application/json" in self.headers.get("accept", "")

    @property
    def is_xhr(self) -> bool:
        """
        Is true when the request is a XMLHttpRequest.
        It works if JavaScript's HTTP client sets an X-Requested-With HTTP header.
        Known frameworks:
        http://en.wikipedia.org/wiki/List_of_Ajax_frameworks#JavaScript
        :return:
        """
        return self.headers.get("x-requested-with", None) == "XMLHttpRequest"

    @property
    def ip(self) -> str:
        """Returns the IP address of user."""
        return self.client.host

    @property
    def secure(self) -> bool:
        """Determine if the request served over SSL."""
        return self.scope["scheme"] == "https"

    @property
    def is_post(self) -> bool:
        """Test if request was made using POST command."""
        return self.method.upper() == "POST"

    @property
    def session(self) -> Session:
        assert "session" in self.scope, "SessionMiddleware must be installed to access request.session"
        return self.scope['session']

    @property
    def old_input(self) -> OldFormInput:
        """Get previous form input. This value does not include uploaded files."""
        return OldFormInput(self.session.pop('_form_old_input', {}))

    async def remember_form_data(self) -> None:
        """Flush current form data into session so it can be used on the next page to render form errors."""
        data = await self.form()
        self.session['_form_old_input'] = {k: v for k, v in data.items() if not isinstance(v, ds.UploadFile)}

    @property
    def form_errors(self) -> FormErrors:
        """Get form errors generated on the previous page."""
        return FormErrors(self.session.pop('_form_error', ''), self.session.pop('_form_field_errors', {}))

    def set_form_errors(self, error_message: str = '', field_errors: dict = None) -> None:
        """Flush form error message and form field errors into session.
        This data can be later retrieved via `request.form_errors` attribute."""
        self.session['_form_error'] = error_message
        self.session['_form_field_errors'] = field_errors or {}

    def url_matches(self, *patterns: t.Union[str, t.Pattern]) -> bool:
        for pattern in patterns:
            if pattern == self.url.path:
                return True
            if re.match(pattern, self.url.path):
                return True
        return False

    def full_url_matches(self, *patterns: t.Union[str, t.Pattern]) -> bool:
        for pattern in patterns:
            if pattern == str(self.url):
                return True
            if re.match(pattern, str(self.url)):
                return True
        return False

    async def form(self) -> FormData:
        data = await super().form()
        return FormData(
            [
                (k, UploadFile.from_base_upload_file(v) if isinstance(v, ds.UploadFile) else v)
                for k, v in data.multi_items()
            ]
        )

    async def files(self) -> FilesData:
        data = await self.form()
        return FilesData(FormData([(k, v) for k, v in data.multi_items() if isinstance(v, UploadFile)]))
