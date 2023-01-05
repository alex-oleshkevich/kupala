from __future__ import annotations

import dataclasses

import contextlib
import functools
import inspect
import typing
from starlette.concurrency import run_in_threadpool
from starlette.requests import HTTPConnection


class InjectionError(Exception):
    ...


class InvalidInjection(InjectionError):
    ...


@dataclasses.dataclass
class _Context:
    conn: HTTPConnection
    param_name: str
    type: type
    default_value: typing.Any
    optional: bool = False


Context = typing.Annotated[_Context, lambda: None]


def resolve_context(conn: HTTPConnection, dependency: Dependency) -> Context:
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
    is_async: bool
    default_value: typing.Any
    factory: typing.Callable
    plan: InjectionPlan | None = None

    async def execute(self, conn: HTTPConnection) -> typing.Any:
        if self.plan is None:
            self.plan = InjectionPlan.from_callable(self.factory)
            for name, dependency in self.plan.dependencies.items():
                if dependency.type == _Context:
                    dependency.plan = InjectionPlan.from_callable(functools.partial(resolve_context, conn, dependency))

        return await self.plan.execute(conn)

    @classmethod
    def from_parameter(cls, parameter: inspect.Parameter) -> Dependency:
        annotation = parameter.annotation
        origin = typing.get_origin(parameter.annotation) or parameter.annotation

        optional = False
        if origin is typing.Union:
            optional = type(None) in typing.get_args(parameter.annotation)
            annotation = next((arg for arg in typing.get_args(parameter.annotation) if arg is not None))

        base_type, factory = typing.get_args(annotation)

        return cls(
            param_name=parameter.name,
            factory=factory,
            type=base_type,
            optional=optional,
            default_value=parameter.default,
            is_async=inspect.iscoroutinefunction(factory),
        )


@dataclasses.dataclass
class InjectionPlan:
    fn: typing.Callable
    is_async: bool
    return_annotation: type
    dependencies: dict[str, Dependency] = dataclasses.field(default_factory=dict)

    async def execute(self, conn: HTTPConnection) -> typing.Any:
        dependencies: dict[str, typing.Any] = {}
        for param_name, dependency in self.dependencies.items():
            value = await dependency.execute(conn)
            if value is None and not dependency.optional:
                raise InvalidInjection(
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
    def from_callable(cls, fn: typing.Callable) -> InjectionPlan:
        signature = inspect.signature(fn)
        parameters = dict(signature.parameters)

        plan = cls(fn=fn, return_annotation=signature.return_annotation, is_async=inspect.iscoroutinefunction(fn))
        for param_name, parameter in parameters.items():
            plan.dependencies[param_name] = Dependency.from_parameter(parameter)

        return plan
