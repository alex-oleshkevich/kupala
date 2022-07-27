from __future__ import annotations

import mimetypes
import os
import pathlib
import re
import typing
import uuid
from babel.core import Locale
from imia import AnonymousUser, LoginState, UserLike, UserToken
from starlette import datastructures as ds, requests
from starlette.requests import empty_receive, empty_send
from starlette.types import Receive, Scope, Send
from starsessions import Session

from kupala.storages.storages import Storage

if typing.TYPE_CHECKING:
    from kupala.application import App


class QueryParams(requests.QueryParams):
    def get_bool(self, key: str, default: bool = None) -> bool | None:
        value = self.get(key, None)
        return value.lower() in ['t', 'true', 'yes', 'on', '1'] if value is not None else default

    def get_list(self, key: str, subcast: typing.Callable = None) -> list[str]:
        items = self.getlist(key)
        if subcast:
            return list(map(subcast, items))
        return items

    def get_int(self, key: str, default: int = None) -> typing.Optional[int]:
        value: str = self.get(key, '')
        return int(value) if value != '' and value.isnumeric() else default


class FormData(requests.FormData):
    pass


class UploadFile(ds.UploadFile):
    @classmethod
    def from_base_upload_file(cls, upload_file: ds.UploadFile) -> UploadFile:
        return UploadFile(
            filename=upload_file.filename,
            file=upload_file.file,
            content_type=upload_file.content_type,
        )

    async def save(self, storage: Storage, directory: str | os.PathLike, filename: str | None = None) -> str:
        uploaded_filename = pathlib.Path(self.filename)
        extension = pathlib.Path(uploaded_filename).suffix
        base_name = os.path.basename(uploaded_filename).replace(extension, '')
        prefix = str(uuid.uuid4().fields[-1])[:5]
        if not extension:
            extension = '.' + (mimetypes.guess_extension(self.content_type) or 'bin')
        extension = extension.lstrip('.')
        suggested_filename = f'{prefix}_{base_name}.{extension}'

        file_path = os.path.join(directory, filename or suggested_filename)
        await storage.put(file_path, await self.read())
        return file_path

    async def read(self, size: int = -1) -> bytes:
        return typing.cast(bytes, await super().read(size))

    async def read_string(self, size: int = -1, encoding: str = 'utf8', errors: str = 'strict') -> str:
        return (await self.read(size)).decode(encoding, errors)


class FilesData:
    def __init__(self, files: FormData) -> None:
        self._files = files

    def get(self, key: str, default: typing.Any = None) -> UploadFile | None:
        value = self._files.get(key, default)
        assert isinstance(value, UploadFile)
        return value

    def getlist(self, key: str) -> list[UploadFile]:
        return typing.cast(list[UploadFile], self._files.getlist(key))


class Cookies(dict):
    pass


class Headers(requests.Headers):
    pass


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
    def id(self) -> str:
        assert 'request_id' in self.scope, 'RequestIDMiddleware must be installed to access request.id'
        return self.scope['request_id']

    @property
    def query_params(self) -> QueryParams:
        return QueryParams(super().query_params)

    @property
    def app(self) -> 'App':
        return self.scope['app']

    @property
    def auth(self) -> UserToken:
        return self.scope.get('auth', UserToken(user=AnonymousUser(), state=LoginState.ANONYMOUS))

    @property
    def user(self) -> UserLike:
        return self.auth.user

    @property
    def wants_json(self) -> bool:
        """Test if request sends Accept header with 'application/json' value."""
        return "application/json" in self.headers.get("accept", "")

    @property
    def is_json(self) -> bool:
        return "application/json" in self.headers.get("content-type", "")

    @property
    def is_xhr(self) -> bool:
        """
        Is true when the request is a XMLHttpRequest. It works if JavaScript's
        HTTP client sets an X-Requested-With HTTP header. Known frameworks:
        http://en.wikipedia.org/wiki/List_of_Ajax_frameworks#JavaScript.

        :return:
        """
        return self.headers.get("x-requested-with", None) == "XMLHttpRequest"

    @property
    def ip(self) -> str:
        """Returns the IP address of user."""
        assert self.client, 'Client address is unknown.'
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
    def locale(self) -> Locale:
        assert "locale" in self.scope, "LocaleMiddleware must be installed to access request.locale"
        return self.scope['locale']

    @property
    def language(self) -> str:
        return self.locale.language

    @property
    def cookies(self) -> Cookies:
        return Cookies(**super().cookies)

    @property
    def headers(self) -> Headers:
        return Headers(super().headers)

    @property
    def is_submitted(self) -> bool:
        return self.method.lower() in ['post', 'put', 'patch', 'delete']

    def url_matches(self, *patterns: str | typing.Pattern) -> bool:
        for pattern in patterns:
            if pattern == self.url.path:
                return True
            if re.search(pattern, self.url.path):
                return True
        return False

    def full_url_matches(self, *patterns: str | typing.Pattern) -> bool:
        for pattern in patterns:
            if pattern == str(self.url):
                return True
            if re.match(pattern, str(self.url)):
                return True
        return False

    def static_url(self, path: str, path_name: str = 'static') -> str:
        """Generate a URL to a static file."""
        return self.url_for(path_name, path=path)

    def url_for(self, name: str, **path_params: typing.Any) -> str:
        return self.app.url_for(name, **path_params)

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

    async def data(self) -> typing.Mapping:
        """
        Returns a request data.

        Automatically decodes JSON if Content-Type is application/json.
        """
        if self.is_json:
            return await self.json()
        return await self.form()

    def __repr__(self) -> str:
        return f'<{self.__class__.__name__}: {self.method} {self.url}>'
