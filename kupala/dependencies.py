import annotationlib
import contextlib
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

# why the injector cannot fill each unsupported parameter kind
UNSUPPORTED_PARAMETER_KINDS: dict[inspect._ParameterKind, str] = {
    inspect.Parameter.POSITIONAL_ONLY: (
        "Dependencies are passed by keyword, so use a regular or keyword-only parameter."
    ),
    inspect.Parameter.VAR_POSITIONAL: (
        "The injector passes a fixed set of named arguments, so *args can never be filled."
    ),
    inspect.Parameter.VAR_KEYWORD: (
        "The injector passes a fixed set of named arguments, so **kwargs can never be filled."
    ),
}


def callable_name(fn: typing.Any) -> str:
    """Render a callable as `module.qualname` for error messages."""

    name: str = getattr(fn, "__qualname__", None) or type(fn).__name__
    module: str | None = getattr(fn, "__module__", None)
    return f"{module}.{name}" if module else name


def type_name(key: typing.Any) -> str:
    """Render a binding key the way a developer wrote it in the annotation."""

    return typing.cast(str, getattr(key, "__qualname__", None) or repr(key))


class DependencyError(Exception):
    """Base class for every dependency injection error."""


class InvalidDependencyError(DependencyError):
    """A callable cannot be injected at all. Raised while compiling the call plan."""


class UnsupportedParameterError(InvalidDependencyError):
    """A parameter uses a calling convention the injector cannot fill."""

    def __init__(self, param: ParamInfo, owner: str) -> None:
        super().__init__(
            f"Cannot inject parameter {param.name!r} of {owner}(). {UNSUPPORTED_PARAMETER_KINDS[param.kind]}"
        )


class UnannotatedParameterError(InvalidDependencyError):
    """A parameter has neither a type annotation nor a default, so nothing identifies it."""

    def __init__(self, param: ParamInfo, owner: str) -> None:
        super().__init__(
            f"Parameter {param.name!r} of {owner}() has no type annotation. "
            f"Annotate it so the injector knows what to provide, or give it a default value."
        )


class AmbiguousBindingError(InvalidDependencyError):
    """A parameter carries more than one binding, so the injector cannot tell which one to use."""

    def __init__(self, param: ParamInfo, owner: str, bindings: tuple[Binding, ...]) -> None:
        listed = ", ".join(repr(binding) for binding in bindings)
        super().__init__(
            f"Parameter {param.name!r} of {owner}() has {len(bindings)} bindings: {listed}. "
            f"Annotate it with exactly one."
        )


class CircularDependencyError(InvalidDependencyError):
    """A factory depends on itself, directly or through other factories."""

    def __init__(self, factory: Factory, context: CompileContext) -> None:
        path = " -> ".join(callable_name(entry.factory) for entry in (*context.chain, factory))
        super().__init__(
            f"Circular dependency detected: {path}. "
            f"A factory cannot depend on itself, directly or through another factory."
        )


class UnresolvedDependencyError(DependencyError):
    """Nothing was bound for a requested key and the parameter has no default."""

    def __init__(self, key: typing.Any, *, parameter: str | None = None, owner: str | None = None) -> None:
        super().__init__()
        self.key = key
        self.parameter = parameter
        self.owner = owner

    def __str__(self) -> str:
        where = ""
        if self.parameter:
            where = f" requested by parameter {self.parameter!r}"
            if self.owner:
                where += f" of {self.owner}()"

        return (
            f"No binding for {type_name(self.key)}{where}. "
            f"Bind it on the injection scope, or give the parameter a default value."
        )


@dataclasses.dataclass(frozen=True, slots=True)
class InjectionScope:
    bindings: dict[Key, object]

    def bind(self, type_: Key, value: object) -> None:
        self.bindings[type_] = value


@dataclasses.dataclass(frozen=True, slots=True)
class InvocationContext:
    scope: InjectionScope
    cache: dict[Binding, object] = dataclasses.field(default_factory=dict)
    exit_stack: contextlib.AsyncExitStack = dataclasses.field(default_factory=contextlib.AsyncExitStack)

    async def resolve(self, type_: Key, default: object = MISSING) -> object:
        value = self.scope.bindings.get(type_, default)
        if value is MISSING:
            raise UnresolvedDependencyError(type_)

        return value

    async def __aenter__(self) -> typing.Self:
        await self.exit_stack.__aenter__()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: types.TracebackType | None,
    ) -> None:
        await self.exit_stack.__aexit__(exc_type, exc, traceback)


type Resolver = typing.Callable[[InvocationContext], typing.Awaitable[object]]


@dataclasses.dataclass(frozen=True, slots=True)
class CompileContext:
    """State of compiling one callable: who it is, and the factories we descended through to reach it."""

    owner: str
    chain: tuple[Factory, ...] = ()

    def enter(self, factory: Factory) -> typing.Self:
        """Descend into a factory's own callable."""

        raise NotImplementedError


@typing.runtime_checkable
class Binding(typing.Protocol):
    def compile(self, context: CompileContext, param: ParamInfo) -> Resolver: ...


@dataclasses.dataclass(frozen=True, slots=True)
class Inject:
    def compile(self, context: CompileContext, param: ParamInfo) -> Resolver:
        async def resolve(ctx: InvocationContext) -> object:
            try:
                return await ctx.resolve(param.type, param.default)
            except UnresolvedDependencyError as exc:
                exc.parameter = exc.parameter or param.name
                raise

        return resolve


@dataclasses.dataclass(frozen=True, slots=True)
class Value:
    value: typing.Any

    def compile(self, context: CompileContext, param: ParamInfo) -> Resolver:
        async def resolve(ctx: InvocationContext) -> object:
            return self.value

        return resolve


@dataclasses.dataclass(frozen=True, slots=True)
class Factory:
    """Build a value on demand from a callable, a generator, or an async generator."""

    factory: typing.Callable[..., typing.Any]
    cache: bool = True

    def compile(self, context: CompileContext, param: ParamInfo) -> Resolver:
        raise NotImplementedError


type Injected[T] = typing.Annotated[T, Inject()]


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


def is_async_callable(fn: typing.Any) -> typing.TypeGuard[typing.Callable[..., typing.Awaitable[typing.Any]]]:
    """Detect coroutine functions, including callable objects with an async `__call__`."""

    return inspect.iscoroutinefunction(fn) or inspect.iscoroutinefunction(
        getattr(fn, "__call__", None)  # noqa: B004 - reading the coroutine marker, not a callability test
    )


def is_generator_callable(fn: typing.Any) -> typing.TypeGuard[typing.Callable[..., typing.Iterator[typing.Any]]]:
    """Detect generator functions, including callable objects with a generator `__call__`."""

    raise NotImplementedError


def is_async_generator_callable(
    fn: typing.Any,
) -> typing.TypeGuard[typing.Callable[..., typing.AsyncIterator[typing.Any]]]:
    """Detect async generator functions, including callable objects with one as `__call__`."""

    raise NotImplementedError


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


def is_optional(annotation: typing.Any) -> typing.TypeGuard[types.UnionType]:
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


def compile_call_plan[**PS, R](
    fn: typing.Callable[PS, R],
    context: CompileContext | None = None,
) -> CallPlan[PS, R]:
    info = inspect_callable(fn)
    if context is None:
        context = CompileContext(owner=callable_name(fn))

    for param in info.parameters:
        validate_parameter(param, context.owner)

    return CallPlan(
        callable=info,
        parameters=tuple(compile_parameter(context, param) for param in info.parameters),
    )


def validate_parameter(param: ParamInfo, owner: str) -> None:
    """Reject signatures the injector can never fill, while the route is being compiled."""

    if param.kind in UNSUPPORTED_PARAMETER_KINDS:
        raise UnsupportedParameterError(param, owner)

    if param.type is MISSING and param.default is MISSING:
        raise UnannotatedParameterError(param, owner)


def compile_parameter(context: CompileContext, param: ParamInfo) -> ParameterPlan:
    binding = find_binding(param)
    return ParameterPlan(param=param, resolve=binding.compile(context, param))


def find_binding(param: ParamInfo) -> Binding:
    for candidate in param.metadata:
        if not isinstance(candidate, type) and isinstance(candidate, Binding):
            return candidate

    return Inject()


async def resolve_arguments(plan: CallPlan[..., typing.Any], context: InvocationContext) -> dict[str, object]:
    """Resolve every parameter of a plan into the keyword arguments its callable expects."""

    raise NotImplementedError


@typing.overload
async def invoke[R](plan: CallPlan[..., typing.Awaitable[R]], context: InvocationContext) -> R: ...


@typing.overload
async def invoke[R](plan: CallPlan[..., R | typing.Awaitable[R]], context: InvocationContext) -> R: ...


async def invoke[R](plan: CallPlan[..., typing.Any], context: InvocationContext) -> R:
    try:
        kwargs = {plan_param.param.name: await plan_param.resolve(context) for plan_param in plan.parameters}
    except UnresolvedDependencyError as exc:
        exc.owner = exc.owner or callable_name(plan.callable.callable)
        raise

    if plan.callable.is_async:
        result = await plan.callable.callable(**kwargs)
    else:
        # sync callables must never block the event loop
        result = await run_in_threadpool(plan.callable.callable, **kwargs)

    return typing.cast(R, result)
