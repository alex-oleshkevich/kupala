from __future__ import annotations

import dataclasses

import contextlib
import functools
import inspect
import typing
from starlette.concurrency import run_in_threadpool
from starlette.requests import Request
from starlette.websockets import WebSocket


class DependencyError(Exception):
    ...


class InvalidDependency(DependencyError):
    ...


class NotAnnotatedDependency(DependencyError):
    ...


@dataclasses.dataclass
class _Context:
    conn: Request | WebSocket
    param_name: str
    type: type
    default_value: typing.Any
    optional: bool = False


Context = typing.Annotated[_Context, lambda: None]


def resolve_context(conn: Request | WebSocket, dependency: Dependency) -> Context:
    return Context(
        conn=conn,
        type=dependency.type,
        optional=dependency.optional,
        param_name=dependency.param_name,
        default_value=dependency.default_value,
    )


@dataclasses.dataclass
class Dependency:
    type: type
    param_name: str
    optional: bool
    default_value: typing.Any
    factory: typing.Callable
    is_async: bool = False
    plan: DependencyResolver | None = None

    def __post_init__(self) -> None:
        self.is_async = inspect.iscoroutinefunction(self.factory)

    async def resolve(self, request: Request | WebSocket) -> typing.Any:
        if self.plan is None:
            self.plan = DependencyResolver.from_callable(self.factory)
            for name, dependency in self.plan.dependencies.items():
                if dependency.type == _Context:

                    def resolver() -> Context:
                        return resolve_context(request, self)

                    dependency.plan = DependencyResolver.from_callable(resolver)

        return await self.plan.resolve(request)

    @classmethod
    def from_parameter(cls, parameter: inspect.Parameter) -> Dependency:
        annotation = parameter.annotation
        origin = typing.get_origin(parameter.annotation) or parameter.annotation

        optional = False
        if origin is typing.Union:
            optional = type(None) in typing.get_args(parameter.annotation)
            annotation = next((arg for arg in typing.get_args(parameter.annotation) if arg is not None))
            origin = typing.get_origin(annotation)

        if origin is not typing.Annotated:
            if parameter.name == "context":  # support one-line lambdas
                annotation = Context
            else:
                raise NotAnnotatedDependency(
                    f'Parameter "{parameter.name}" is not an instance of typing.Annotated. '
                    f'It is "{parameter.annotation}".'
                )

        base_type, factory = typing.get_args(annotation)

        return cls(
            param_name=parameter.name,
            factory=factory,
            type=base_type,
            optional=optional,
            default_value=parameter.default,
        )


@dataclasses.dataclass
class DependencyResolver:
    fn: typing.Callable
    is_async: bool
    return_annotation: type
    dependencies: dict[str, Dependency] = dataclasses.field(default_factory=dict)

    async def resolve(self, request: Request | WebSocket) -> typing.Any:
        dependencies: dict[str, typing.Any] = {}
        for param_name, dependency in self.dependencies.items():
            value = await dependency.resolve(request)
            if value is None and not dependency.optional:
                raise InvalidDependency(
                    f'Dependency factory for parameter "{param_name}" returned None '
                    f"however parameter annotation declares it as not optional."
                )
            dependencies[param_name] = value

        if self.is_async:
            result = await self.fn(**dependencies)
        else:
            result = await run_in_threadpool(self.fn, **dependencies)

        if isinstance(result, contextlib.AbstractContextManager):
            with result as final_result:
                return final_result
        if isinstance(result, contextlib.AbstractAsyncContextManager):
            async with result as final_result:
                return final_result

        return result

    @classmethod
    def from_callable(
        cls,
        fn: typing.Callable,
        fallback: typing.Callable[[inspect.Parameter], Dependency | None] | None = None,
        overrides: dict[str, Dependency] | None = None,
    ) -> DependencyResolver:
        if isinstance(fn, functools.partial):
            raise InvalidDependency(f"Partial functions are not supported. Function: {fn}")

        fn.__annotations__ = typing.get_type_hints(fn, include_extras=True)
        overrides = overrides or {}
        signature = inspect.signature(fn)
        parameters = dict(signature.parameters)

        plan = cls(fn=fn, return_annotation=signature.return_annotation, is_async=inspect.iscoroutinefunction(fn))
        for param_name, parameter in parameters.items():
            if param_name in overrides:
                plan.dependencies[param_name] = overrides[param_name]
                continue

            try:
                plan.dependencies[param_name] = Dependency.from_parameter(parameter)
            except NotAnnotatedDependency:
                if fallback:
                    if dependency := fallback(parameter):
                        plan.dependencies[param_name] = dependency
                        continue
                raise

        return plan
