from __future__ import annotations

import dataclasses

import contextlib
import functools
import inspect
import types
import typing
from starlette.applications import Starlette
from starlette.concurrency import run_in_threadpool
from starlette.requests import Request

if typing.TYPE_CHECKING:
    pass


class DependencyError(Exception):
    ...


class InvalidDependency(DependencyError):
    ...


class NotAnnotatedDependency(DependencyError):
    ...


@dataclasses.dataclass
class Argument:
    param_name: str
    type: type
    default_value: typing.Any
    optional: bool = False


@dataclasses.dataclass
class InvokeContext:
    app: Starlette
    request: Request | None = None

    def __post_init__(self) -> None:
        self.exit_stack = contextlib.ExitStack()
        self.aexit_stack = contextlib.AsyncExitStack()


@dataclasses.dataclass
class Dependency:
    type: type
    param_name: str
    optional: bool
    default_value: typing.Any
    factory: typing.Callable
    dependencies: dict[str, Dependency] = dataclasses.field(default_factory=dict)

    def __post_init__(self) -> None:
        self._extra_dependencies_map: dict[typing.Literal["argument"], typing.Any] = {}

        signature = inspect.signature(self.factory, eval_str=True)
        for parameter in signature.parameters.values():
            if any(
                [
                    parameter.annotation == Argument,
                    parameter.annotation == parameter.empty and parameter.name == "argument",
                ]
            ):
                self._extra_dependencies_map["argument"] = parameter.name
                continue

            self.dependencies[parameter.name] = Dependency.from_parameter(parameter)

    async def resolve(self, context: InvokeContext) -> typing.Any:
        dependencies: dict[str, typing.Any] = {}
        for dependency in self.dependencies.values():
            dependencies[dependency.param_name] = await dependency.resolve(context)

        if param_name := self._extra_dependencies_map.get("argument"):
            dependencies[param_name] = Argument(
                type=self.type,
                optional=self.optional,
                param_name=self.param_name,
                default_value=self.default_value,
            )

        if inspect.iscoroutinefunction(self.factory):
            value = await self.factory(**dependencies)
        else:
            value = await run_in_threadpool(self.factory, **dependencies)

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
        if origin is typing.Union or origin is types.UnionType:  # noqa: E721, example - (id: FromPath[int] | None)
            optional = type(None) in typing.get_args(parameter.annotation)
            annotation = next((arg for arg in typing.get_args(parameter.annotation) if arg is not None))
            _origin = typing.get_origin(annotation)
            if _origin:
                origin = _origin
            else:
                origin = annotation

        # We allow simpler declaration of Context, Request, and Starlette objects.
        # They can be injected using their classes instead of Annotated.
        if any(
            [
                parameter.name in ["request", "app", "context"],
                origin == Request,
                origin == Argument,
                origin == Starlette,
                inspect.isclass(origin) and issubclass(origin, Request),
                inspect.isclass(origin) and issubclass(origin, Starlette),
            ]
        ):
            return PredefinedDependency(
                param_name=parameter.name,
                factory=lambda: None,
                type=origin,
                optional=optional,
                default_value=parameter.default,
            )

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
class PredefinedDependency(Dependency):
    async def resolve(self, context: InvokeContext) -> typing.Any:
        from kupala.applications import Kupala

        if any(
            [
                self.type == Request or (inspect.isclass(self.type) and issubclass(self.type, Request)),
                self.type == inspect.Parameter.empty and self.param_name == "request",
            ]
        ):
            if context.request is None and self.optional:
                return None

            assert context.request
            request = context.request
            if self.type != inspect.Parameter.empty and self.type != Request:
                request = self.type(request.scope, request.receive, request._send)
            return request

        if any(
            [
                self.type == Starlette or (inspect.isclass(self.type) and issubclass(self.type, Starlette)),
                self.type == Kupala or (inspect.isclass(self.type) and issubclass(self.type, Kupala)),
                self.type == inspect.Parameter.empty and self.param_name == "app",
            ]
        ):
            return context.app


@dataclasses.dataclass
class DependencyResolver:
    fn: typing.Callable
    dependencies: dict[str, Dependency] = dataclasses.field(default_factory=dict)

    async def execute(self, context: InvokeContext) -> typing.Any:
        with context.exit_stack:
            async with context.aexit_stack:
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
