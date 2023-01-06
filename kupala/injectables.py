import typing
from starlette.datastructures import QueryParams
from starlette.requests import Request

from kupala.routing import Context

_T = typing.TypeVar("_T")


def _from_query(context: Context) -> QueryParams:
    return context.type(**context.request.query_params)


FromQuery = typing.Annotated[_T, _from_query]


async def _from_json_body(context: Context) -> typing.Any:
    request = Request(context.request.scope, context.request.receive)
    body = await request.json()
    return context.type(**body)


JSON = typing.Annotated[_T, _from_json_body]


async def _from_form_data(context: Context) -> typing.Any:
    request = Request(context.request.scope, context.request.receive)
    body = await request.form()
    return context.type(**body)


FormData = typing.Annotated[_T, _from_form_data]
CurrentUser = typing.Annotated[_T, lambda context: context.request.user]


def _from_path(context: Context) -> typing.Any:
    value = context.request.path_params.get(context.param_name)
    if value is None:
        if not context.optional:
            raise ValueError(f'Path param "{context.param_name}" is None and no default value defined.')
        return value

    return context.type(value)


FromPath = typing.Annotated[_T, _from_path]
