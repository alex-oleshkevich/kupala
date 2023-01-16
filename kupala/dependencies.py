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
class Context:
    request: Request | WebSocket
    param_name: str
    type: type
    default_value: typing.Any
    optional: bool = False


@dataclasses.dataclass
class InvokeContext:
    exit_stack: contextlib.ExitStack
    aexit_stack: contextlib.AsyncExitStack
    extras: dict[str, typing.Any]

    @property
    def request(self) -> Request | WebSocket:
        return self.extras["request"]


@dataclasses.dataclass
class Dependency:
    type: type
    param_name: str
    optional: bool
    default_value: typing.Any
    factory: typing.Callable[[Context], typing.Any]
    dependencies: dict[str, Dependency] = dataclasses.field(default_factory=dict)
    _requires_context: bool = False

    def __post_init__(self) -> None:
        signature = inspect.signature(self.factory, eval_str=True)
        for parameter in signature.parameters.values():
            if parameter.annotation == Context:
                self._requires_context = True
                continue
            if parameter.annotation == parameter.empty and parameter.name in ["context", "_"]:
                self._requires_context = True
                continue

            self.dependencies[parameter.name] = Dependency.from_parameter(parameter)

    async def resolve(self, context: InvokeContext) -> typing.Any:
        dependencies: dict[str, typing.Any] = {}
        for dependency in self.dependencies.values():
            dependencies[dependency.param_name] = await dependency.resolve(context)

        args: list[typing.Any] = []
        if self._requires_context:
            args.append(
                Context(
                    request=context.request,
                    type=self.type,
                    optional=self.optional,
                    param_name=self.param_name,
                    default_value=self.default_value,
                )
            )
        if inspect.iscoroutinefunction(self.factory):
            value = await self.factory(*args, **dependencies)
        else:
            value = await run_in_threadpool(self.factory, *args, **dependencies)

        if value is None and not self.optional:
            raise InvalidDependency(
                f'Dependency factory for parameter "{self.param_name}" returned None '
                f"however parameter annotation declares it as not optional."
            )

        if isinstance(value, contextlib.AbstractContextManager):
            return context.exit_stack.enter_context(value)
        elif isinstance(value, contextlib.AbstractAsyncContextManager):
            return await context.aexit_stack.enter_async_context(value)
        else:
            return value

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
    dependencies: dict[str, Dependency] = dataclasses.field(default_factory=dict)

    async def execute(self, request: Request | WebSocket | None) -> typing.Any:
        with contextlib.ExitStack() as exit_stack:
            async with contextlib.AsyncExitStack() as aexit_stack:
                context = InvokeContext(extras={"request": request}, exit_stack=exit_stack, aexit_stack=aexit_stack)
                dependencies = {
                    dependency.param_name: await dependency.resolve(context)
                    for dependency in self.dependencies.values()
                }
                if inspect.iscoroutinefunction(self.fn):
                    return await self.fn(**dependencies)
                return await run_in_threadpool(self.fn, **dependencies)

    @classmethod
    def from_callable(cls, fn: typing.Callable, overrides: dict[str, Dependency] | None = None) -> DependencyResolver:
        if isinstance(fn, functools.partial):
            raise InvalidDependency(f"Partial functions are not supported. Function: {fn}")

        overrides = overrides or {}
        signature = inspect.signature(fn, eval_str=True)
        parameters = dict(signature.parameters)

        plan = cls(fn=fn)
        for param_name, parameter in parameters.items():
            if param_name in overrides:
                dependency = overrides[param_name]
            else:
                dependency = Dependency.from_parameter(parameter)
            plan.dependencies[param_name] = dependency

        return plan
