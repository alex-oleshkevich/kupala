from __future__ import annotations

import mimetypes
import os
import pathlib
import re
import typing
import typing as t
import uuid
from deesk.storage import Storage
from imia import UserLike, UserToken
from starlette import datastructures as ds, requests
from starlette.requests import empty_receive, empty_send
from starlette.types import Receive, Scope, Send
from starsessions import Session

from kupala.disks.storages import Storages

if t.TYPE_CHECKING:
    from .application import Kupala


class OldFormInput(t.Mapping):
    def __init__(self, data: dict) -> None:
        self._data = data

    def get(self, key: str, default: t.Any = None) -> t.Any:
        return self._data.get(key, default)

    def to_json(self) -> dict:
        return self._data

    def __getitem__(self, item: str) -> t.Any:
        return self._data[item]

    def __len__(self) -> int:
        return len(self._data)

    def __iter__(self) -> t.Iterator[t.Tuple[str, t.Any]]:
        return iter(self._data)

    def __contains__(self, item: object) -> bool:
        return item in self._data

    def __repr__(self) -> str:
        return f'<OldFormInput: data={self._data}>'

    __call__ = get


class FormErrors(t.Mapping):
    def __init__(self, errors: t.Mapping[str, list[str]]) -> None:
        self.field_errors = errors

    def get(self, key: str, default: t.Any = None) -> t.Optional[list[str]]:
        return self.field_errors.get(key, default)

    def to_json(self) -> dict:
        return {
            'field_errors': self.field_errors,
        }

    def keys(self) -> t.KeysView[str]:
        return self.field_errors.keys()

    def __bool__(self) -> bool:
        return bool(self.field_errors)

    def __getitem__(self, item: str) -> list[str]:
        return self.field_errors[item]

    def __contains__(self, item: object) -> bool:
        return item in self.field_errors

    def __iter__(self) -> t.Iterator:
        return iter(self.field_errors)

    def __len__(self) -> int:
        return len(self.field_errors)

    def __repr__(self) -> str:
        return f'<FormErrors: field_errors={self.field_errors}>'

    __call__ = get


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
    def __init__(self, request: Request, filename: str, file: typing.IO = None, content_type: str = "") -> None:
        self.request = request
        super().__init__(filename, file, content_type)

    @classmethod
    def from_base_upload_file(cls, upload_file: ds.UploadFile, request: Request) -> UploadFile:
        return UploadFile(
            filename=upload_file.filename,
            file=upload_file.file,
            content_type=upload_file.content_type,
            request=request,
        )

    async def save(self, directory: t.Union[str, os.PathLike], filename: str = None, disk: str = None) -> str:
        uploaded_filename = pathlib.Path(self.filename)
        extension = pathlib.Path(uploaded_filename).suffix
        base_name = os.path.basename(uploaded_filename).replace(extension, '')
        prefix = str(uuid.uuid4().fields[-1])[:5]
        if not extension:
            extension = '.' + (mimetypes.guess_extension(self.content_type) or 'bin')
        extension = extension.lstrip('.')
        suggested_filename = f'{prefix}_{base_name}.{extension}'

        file_path = os.path.join(directory, filename or suggested_filename)

        storage: Storage
        if disk:
            storage = self.request.app.resolve(Storages).get(disk)
        else:
            storage = self.request.app.resolve(Storages).get_default_disk()
        await storage.put(file_path, await self.read())
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
            instance.__init__(scope, receive, send)  # type: ignore
            scope['request'] = instance
        elif scope['request'].__class__ != cls:
            # view function uses custom request class
            request = scope['request']
            request.__class__ = cls
            scope['request'] = request
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
    def user(self) -> UserLike:
        return self.auth.user

    @property
    def wants_json(self) -> bool:
        """Test if request sends Accept header
        with 'application/json' value."""
        return "application/json" in self.headers.get("accept", "")

    @property
    def is_json(self) -> bool:
        return "application/json" in self.headers.get("content-type", "")

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
        if '_form_old_input' not in self.scope:
            old_form_input = OldFormInput({})
            if 'session' in self.scope:
                old_form_input = OldFormInput(self.session.pop('_form_old_input', {}))
            self.scope['_form_old_input'] = old_form_input
        return self.scope['_form_old_input']

    async def remember_form_data(self) -> None:
        """Flush current form data into session so it can be used on the next page to render form errors."""
        if 'session' in self.scope:
            data = await self.form()
            self.session['_form_old_input'] = {k: v for k, v in data.items() if not isinstance(v, ds.UploadFile)}

    @property
    def form_errors(self) -> FormErrors:
        """Get form errors generated on the previous page."""
        if '_form_error' not in self.scope:
            form_error = FormErrors({})
            if 'session' in self.scope:
                form_error = FormErrors(self.session.pop('_form_field_errors', {}))
            self.scope['_form_error'] = form_error
        return self.scope['_form_error']

    def set_form_errors(self, field_errors: dict = None) -> None:
        """Flush form error message and form field errors into session.
        This data can be later retrieved via `request.form_errors` attribute."""
        if 'session' in self.scope:
            self.session['_form_field_errors'] = field_errors or {}

    def url_matches(self, *patterns: t.Union[str, t.Pattern]) -> bool:
        for pattern in patterns:
            if pattern == self.url.path:
                return True
            if re.search(pattern, self.url.path):
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
                (k, UploadFile.from_base_upload_file(v, self) if isinstance(v, ds.UploadFile) else v)
                for k, v in data.multi_items()
            ]
        )

    async def files(self) -> FilesData:
        data = await self.form()
        return FilesData(FormData([(k, v) for k, v in data.multi_items() if isinstance(v, UploadFile)]))

    async def data(self) -> t.Mapping:
        """Returns a request data.
        Automatically decodes JSON if Content-Type is application/json."""
        if self.is_json:
            return await self.json()
        return await self.form()

    def __repr__(self) -> str:
        return f'<{self.__class__.__name__}: {self.method} {self.url}>'
