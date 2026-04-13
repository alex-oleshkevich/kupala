import typing

from starlette_dispatch.contrib.dependencies import PathParamValue

from kupala.dependency_resolvers import (
    FormDataResolver,
    JSONDataResolver,
    QueryParamResolver,
)
from kupala.encryptors import Encryptor as _Encryptor
from kupala.files import Files as _Files
from kupala.mail import Mail as _Mail
from kupala.passwords import Passwords as _Passwords
from kupala.templating import Templates as _Templates

T = typing.TypeVar("T")


Files = typing.Annotated[_Files, lambda r: _Files.of(r)]
Passwords = typing.Annotated[_Passwords, lambda r: _Passwords.of(r)]
Encryptor = typing.Annotated[_Encryptor, lambda r: _Encryptor.of(r)]
Templates = typing.Annotated[_Templates, lambda r: _Templates.of(r)]
Mail = typing.Annotated[_Mail, lambda r: _Mail.of(r)]
FromPath = typing.Annotated[T, PathParamValue()]
CurrentUser = typing.Annotated[T, lambda request: request.user]
FromQuery = typing.Annotated[T, QueryParamResolver()]
FromForm = typing.Annotated[T, FormDataResolver()]
FromJSON = typing.Annotated[T, JSONDataResolver()]
