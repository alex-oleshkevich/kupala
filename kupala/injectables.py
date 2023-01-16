import typing
from starlette.datastructures import QueryParams
from starlette.requests import Request

from kupala.dependencies import Argument

_T = typing.TypeVar("_T")


def _from_query(argument: Argument, request: Request) -> QueryParams:
    return argument.type(**request.query_params)


FromQuery = typing.Annotated[_T, _from_query]


async def _from_json_body(argument: Argument, request: Request) -> typing.Any:
    body = await request.json()
    return argument.type(**body)


JSON = typing.Annotated[_T, _from_json_body]


async def _from_form_data(argument: Argument, request: Request) -> typing.Any:
    body = await request.form()
    return argument.type(**body)


FormData = typing.Annotated[_T, _from_form_data]
CurrentUser = typing.Annotated[_T, lambda request: request.user]


def _from_path(argument: Argument, request: Request) -> typing.Any:
    value = request.path_params.get(argument.param_name)
    if value is None:
        if not argument.optional:
            raise ValueError(f'Path param "{argument.param_name}" is None and no default value defined.')
        return value

    return argument.type(value)


FromPath = typing.Annotated[_T, _from_path]
