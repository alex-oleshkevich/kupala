import typing

from starlette.requests import HTTPConnection, Request
from starlette.websockets import WebSocket
from starlette_dispatch import (
    DependencyError,
    DependencyResolver,
    DependencyScope,
    DependencySpec,
    FactoryResolver,
    RequestResolver,
    ResolveContext,
    VariableResolver,
)
from starlette_dispatch.contrib.dependencies import PathParamValue

__all__ = [
    "DependencyError",
    "DependencyResolver",
    "DependencySpec",
    "FactoryResolver",
    "RequestResolver",
    "VariableResolver",
    "PathParamValue",
    "QueryParamResolver",
    "JSONDataResolver",
    "FormDataResolver",
    "ResolveContext",
    "DependencyScope",
]


class QueryParamResolver(DependencyResolver):
    async def resolve(self, spec: DependencySpec, overrides: dict[typing.Any, typing.Any]) -> typing.Any:
        conn: HTTPConnection | None = overrides.get(Request, overrides.get(WebSocket))
        if not conn:
            raise DependencyError(f'Cannot extract path parameter "{spec.param_name}": no HTTP connection found.')

        value = conn.query_params.get(spec.param_name)
        return self.spec.param_type(value) if value is not None else None


class JSONDataResolver(DependencyResolver):
    async def resolve(self, spec: DependencySpec, overrides: dict[typing.Any, typing.Any]) -> typing.Any:
        request: Request = overrides[Request]
        body = await request.json()
        return spec.param_type(**body)


class FormDataResolver(DependencyResolver):
    async def resolve(self, spec: DependencySpec, overrides: dict[typing.Any, typing.Any]) -> typing.Any:
        request: Request = overrides[Request]
        body = await request.form()
        return spec.param_type(**body)
