import typing

from starlette_dispatch.contrib.dependencies import PathParamValue

from kupala.crypto import Encryptor as _Encryptor
from kupala.crypto import Passwords as _Passwords
from kupala.mail import Mail as _Mail
from kupala.templating import Templates as _Templates

T = typing.TypeVar("T")


FromPath = typing.Annotated[T, PathParamValue()]
Passwords = typing.Annotated[_Passwords, lambda r: _Passwords.of(r)]
Encryptor = typing.Annotated[_Encryptor, lambda r: _Encryptor.of(r)]
Templates = typing.Annotated[_Templates, lambda r: _Templates.of(r)]
Mail = typing.Annotated[_Mail, lambda r: _Mail.of(r)]
