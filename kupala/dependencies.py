import typing

from kupala.authentication import AuthToken

_T = typing.TypeVar('_T')
FromQuery = typing.Annotated[_T, lambda request: request.query_params]
FromQueryParam = typing.Annotated[_T, lambda request: request.query_params]
FromHeader = typing.Annotated[_T, lambda request: request.query_params]
FromHeaders = typing.Annotated[_T, lambda request: request.query_params]
FromCookie = typing.Annotated[_T, lambda request: request.query_params]
FromCookies = typing.Annotated[_T, lambda request: request.query_params]
FromPath = typing.Annotated[_T, lambda request: request.query_params]
CurrentUser = typing.Annotated[_T, lambda request: request.user]
Auth = typing.Annotated[AuthToken, lambda request: request.auth]
