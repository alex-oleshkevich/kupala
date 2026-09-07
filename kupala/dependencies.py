import annotationlib
import dataclasses
import functools
import inspect
import operator
import types
import typing

from starlette.concurrency import run_in_threadpool

type Key = type[typing.Any]

INVOCATION_CONTEXT_KEY = "kupala.invocation_context"

MISSING = object()


@dataclasses.dataclass(frozen=True, slots=True)
class InjectionScope:
    bindings: dict[Key, object]

    def bind(self, type_: Key, value: object) -> None:
        self.bindings[type_] = value


@dataclasses.dataclass(frozen=True, slots=True)
class InvocationContext:
    scope: InjectionScope

    async def resolve(self, type_: Key, default: object = MISSING) -> object:
        value = self.scope.bindings.get(type_, default)
        if value is MISSING:
            raise KeyError(type_)

        return value


type Resolver = typing.Callable[[InvocationContext], typing.Awaitable[object]]


@typing.runtime_checkable
class Binding(typing.Protocol):
    def compile(self, param: ParamInfo) -> Resolver: ...


@dataclasses.dataclass(frozen=True, slots=True)
class Inject:
    def compile(self, param: ParamInfo) -> Resolver:
        async def resolve(ctx: InvocationContext) -> object:
            return await ctx.resolve(param.type, param.default)

        return resolve


@dataclasses.dataclass(frozen=True, slots=True)
class Value:
    value: typing.Any

    def compile(self, param: ParamInfo) -> Resolver:
        async def resolve(ctx: InvocationContext) -> object:
            return self.value

        return resolve


type Injected[T] = typing.Annotated[T, Inject()]


class DependencyRegistry:
    def provide(self, type_: object, value: object) -> None:
        pass


@dataclasses.dataclass
class ParamInfo:
    name: str
    type: typing.Any
    kind: inspect._ParameterKind
    annotation: typing.Any
    default: typing.Any = MISSING
    metadata: tuple[typing.Any, ...] = ()

    @property
    def optional(self) -> bool:
        return self.default is not MISSING


@dataclasses.dataclass(frozen=True)
class CallableInfo[**PS, R]:
    callable: typing.Callable[PS, R]
    parameters: tuple[ParamInfo, ...]
    return_type: typing.Any
    is_async: bool


def parse_parameter(param: inspect.Parameter) -> ParamInfo:
    type_, metadata = unwrap_annotation(param.annotation)
    default = param.default if param.default is not inspect.Parameter.empty else MISSING

    if is_optional(type_):
        type_ = strip_none(type_)
        if default is MISSING:
            default = None

    if type_ is inspect.Parameter.empty:
        type_ = MISSING

    return ParamInfo(
        type=type_,
        name=param.name,
        kind=param.kind,
        metadata=metadata,
        default=default,
        annotation=param.annotation if param.annotation is not inspect.Parameter.empty else MISSING,
    )


def is_async_callable(fn: typing.Any) -> bool:
    """Detect coroutine functions, including callable objects with an async `__call__`."""

    return inspect.iscoroutinefunction(fn) or inspect.iscoroutinefunction(
        getattr(fn, "__call__", None)  # noqa: B004 - reading the coroutine marker, not a callability test
    )


def inspect_callable[**PS, R](fn: typing.Callable[PS, R]) -> CallableInfo[PS, R]:
    signature = inspect.signature(fn, annotation_format=annotationlib.Format.FORWARDREF)
    return_type = signature.return_annotation
    return CallableInfo(
        callable=fn,
        parameters=tuple(parse_parameter(param) for param in signature.parameters.values()),
        return_type=MISSING if return_type is inspect.Signature.empty else return_type,
        is_async=is_async_callable(fn),
    )


def unwrap_alias(annotation: typing.Any) -> typing.Any:
    """Resolve type aliases, including subscripted ones like `Injected[str]`."""

    while True:
        if isinstance(annotation, typing.TypeAliasType):
            annotation = annotationlib.call_evaluate_function(
                annotation.evaluate_value,
                format=annotationlib.Format.FORWARDREF,
            )
            continue

        origin = typing.get_origin(annotation)
        if isinstance(origin, typing.TypeAliasType):
            annotation = unwrap_alias(origin)[typing.get_args(annotation)]
            continue

        return annotation


def unwrap_annotation(annotation: typing.Any) -> tuple[typing.Any, tuple[typing.Any, ...]]:
    """Strip aliases and `Annotated` layers, collecting metadata innermost first."""

    metadata: list[typing.Any] = []
    while True:
        annotation = unwrap_alias(annotation)
        if typing.get_origin(annotation) is not typing.Annotated:
            return annotation, tuple(metadata)

        annotation, *extra = typing.get_args(annotation)
        metadata[:0] = extra


def is_optional(annotation: typing.Any) -> bool:
    return isinstance(annotation, types.UnionType) and types.NoneType in typing.get_args(annotation)


def strip_none(annotation: typing.Any) -> typing.Any:
    args = (arg for arg in typing.get_args(annotation) if arg is not types.NoneType)
    return functools.reduce(operator.or_, args)


@dataclasses.dataclass
class ParameterPlan:
    param: ParamInfo
    resolve: Resolver


@dataclasses.dataclass
class CallPlan[**PS, R]:
    callable: CallableInfo[PS, R]
    parameters: tuple[ParameterPlan, ...]


def compile_call_plan[**PS, R](fn: typing.Callable[PS, R]) -> CallPlan[PS, R]:
    info = inspect_callable(fn)
    return CallPlan(
        callable=info,
        parameters=tuple(compile_parameter(param) for param in info.parameters),
    )


def compile_parameter(param: ParamInfo) -> ParameterPlan:
    binding = find_binding(param)
    return ParameterPlan(param=param, resolve=binding.compile(param))


def find_binding(param: ParamInfo) -> Binding:
    for candidate in param.metadata:
        if not isinstance(candidate, type) and isinstance(candidate, Binding):
            return candidate

    return Inject()


@typing.overload
async def invoke[R](plan: CallPlan[..., typing.Awaitable[R]], context: InvocationContext) -> R: ...


@typing.overload
async def invoke[R](plan: CallPlan[..., R | typing.Awaitable[R]], context: InvocationContext) -> R: ...


async def invoke[R](plan: CallPlan[..., typing.Any], context: InvocationContext) -> R:
    kwargs = {plan_param.param.name: await plan_param.resolve(context) for plan_param in plan.parameters}
    if plan.callable.is_async:
        result = await plan.callable.callable(**kwargs)
    else:
        # sync callables must never block the event loop
        result = await run_in_threadpool(plan.callable.callable, **kwargs)

    return typing.cast(R, result)
