import typing
from starlette.datastructures import QueryParams

from kupala.authentication import AuthToken
from kupala.routing import Context

_T = typing.TypeVar("_T")


def _from_query(context: Context) -> QueryParams:
    return context.origin(**context.request.query_params)


FromQuery = typing.Annotated[_T, _from_query]


async def _from_json_body(context: Context) -> typing.Any:
    body = await context.request.json()
    return context.origin(**body)


JSON = typing.Annotated[_T, _from_json_body]


async def _from_form_data(context: Context) -> typing.Any:
    body = await context.request.form()
    return context.origin(**body)


FormData = typing.Annotated[_T, _from_form_data]
CurrentUser = typing.Annotated[_T, lambda context: context.request.user]
Auth = typing.Annotated[AuthToken[_T], lambda context: context.request.auth]
