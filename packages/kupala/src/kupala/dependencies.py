import annotationlib
import contextlib
import dataclasses
import functools
import inspect
import logging
import types
import typing

from starlette.concurrency import run_in_threadpool
from starlette.datastructures import State

from kupala import inspection
from kupala.binders import ModelBinder

type Key = type[typing.Any]
type Resolver = typing.Callable[[InvocationContext], typing.Awaitable[object]]

INVOCATION_CONTEXT_KEY = "kupala.invocation_context"

MISSING = object()

logger = logging.getLogger(__name__)


class DependencyError(Exception):
    """Base class for every dependency injection error."""


class InvalidDependencyError(DependencyError):
    """A dependency definition cannot be injected."""


class UnsupportedParameterError(InvalidDependencyError):
    """A parameter uses a calling convention the injector cannot fill."""


class UnannotatedParameterError(InvalidDependencyError):
    """A parameter has neither a type annotation nor a default, so nothing identifies it."""


class AmbiguousBindingError(InvalidDependencyError):
    """A parameter carries more than one binding, so the injector cannot tell which one to use."""


class CircularDependencyError(InvalidDependencyError):
    """A dependency depends on itself, directly or through other dependencies."""


class UnresolvedStateError(DependencyError):
    """Nothing on the invocation state matches the requested key."""


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
            f"No binding for {inspection.type_name(self.key)}{where}. "
            f"Bind it on the injection scope, or give the parameter a default value."
        )


@dataclasses.dataclass(frozen=True, slots=True)
class InjectionScope:
    bindings: dict[Key, Resolver]

    def bind(self, type_: Key, resolver: Resolver) -> None:
        self.bindings[type_] = resolver


@dataclasses.dataclass(slots=True)
class InvocationContext:
    scope: InjectionScope
    state: State = dataclasses.field(default_factory=State)
    cache: dict[Binding, object] = dataclasses.field(default_factory=dict)
    resolving: list[Key] = dataclasses.field(default_factory=list)
    # replacements keyed by the annotation as written, checked before any binding runs
    overrides: typing.Mapping[typing.Any, Binding] = dataclasses.field(default_factory=dict)
    # only set while the context is entered, so a dependency that needs cleanup can tell
    exit_stack: contextlib.AsyncExitStack | None = None

    def child(self, bindings: typing.Mapping[Key, Resolver]) -> typing.Self:
        """Resolve `bindings` ahead of this context's own, sharing everything else with it.

        Only the injection scope is new. The cache, the state, the overrides and the exit stack stay
        the very same objects, so a middleware and the endpoint below it each see their own request
        and continuation while a dependency they both declare is built once and released once.
        """

        return dataclasses.replace(
            self,
            scope=InjectionScope(bindings={**self.scope.bindings, **bindings}),
        )

    async def resolve[T](self, type_: type[T], default: object = MISSING) -> T:
        try:
            resolver = self.scope.bindings[type_]
        except KeyError:
            if default is MISSING:
                raise UnresolvedDependencyError(type_) from None
            return typing.cast(T, default)

        if type_ in self.resolving:
            start = self.resolving.index(type_)
            cycle = (*self.resolving[start:], type_)
            path = " -> ".join(inspection.type_name(key) for key in cycle)
            raise CircularDependencyError(f"Circular dependency detected: {path}.")

        self.resolving.append(type_)
        try:
            return typing.cast(T, await resolver(self))
        finally:
            self.resolving.pop()

    async def __aenter__(self) -> typing.Self:
        self.exit_stack = contextlib.AsyncExitStack()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: types.TracebackType | None,
    ) -> None:
        stack, self.exit_stack = self.exit_stack, None
        if stack is None:  # pragma: no cover - __aexit__ only ever runs after __aenter__
            return

        try:
            await stack.__aexit__(exc_type, exc, traceback)
        except Exception:
            # the response has already been sent, so there is nobody left to tell but the log
            logger.exception("Failed to release a dependency.")


def constant[T](value: T) -> Resolver:
    """Build a resolver that returns one already-constructed value."""

    async def resolve(_context: InvocationContext) -> object:
        return value

    return resolve


@dataclasses.dataclass(frozen=True, slots=True)
class CompileContext:
    """The factories we descended through to reach the callable being compiled."""

    chain: tuple[Factory, ...] = ()
    binders: tuple[ModelBinder, ...] = ()

    def enter(self, factory: Factory) -> typing.Self:
        """Descend into a factory's own callable."""

        return dataclasses.replace(self, chain=(*self.chain, factory))


@typing.runtime_checkable
class Binding(typing.Protocol):
    def compile(self, context: CompileContext, param: ParamInfo) -> Resolver: ...


@typing.runtime_checkable
class DependencyProvider(Binding, typing.Protocol):
    """A binding that exposes nested dependency metadata."""

    def dependency_info(self) -> CallableInfo[..., typing.Any] | None: ...


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
        return constant(self.value)


@dataclasses.dataclass(frozen=True, slots=True)
class FromState[T]:
    """Select a value the lifespan or a middleware left on the invocation state."""

    select: typing.Callable[[InvocationContext, State], T]

    def compile(self, context: CompileContext, param: ParamInfo) -> Resolver:
        async def resolve(ctx: InvocationContext) -> object:
            try:
                return self.select(ctx, ctx.state)
            except AttributeError as exc:
                raise UnresolvedStateError(
                    f"Parameter {param.name!r} reads something the invocation state does not have: {exc}. "
                    f"Set it in the application lifespan or in a middleware."
                ) from exc

        return resolve


@dataclasses.dataclass(frozen=True, slots=True)
class Factory:
    """Build a value on demand from a callable, a generator, or an async generator."""

    factory: typing.Callable[..., typing.Any]
    cache: bool = True

    def dependency_info(self) -> CallableInfo[..., typing.Any]:
        return inspect_callable(self.factory)

    def compile(self, context: CompileContext, param: ParamInfo) -> Resolver:
        if self in context.chain:
            path = " -> ".join(inspection.callable_name(entry.factory) for entry in (*context.chain, self))
            raise CircularDependencyError(
                f"Circular dependency detected: {path}. "
                f"A factory cannot depend on itself, directly or through another factory."
            )

        # compiling eagerly means a broken factory fails on import, not on the first request
        plan = compile_call_plan(self.factory, context.enter(self))
        open_dependency = open_dependency_for(self.factory)

        async def resolve(ctx: InvocationContext) -> object:
            if self.cache and self in ctx.cache:
                return ctx.cache[self]

            arguments = await resolve_arguments(plan, ctx)
            if open_dependency is None:
                value = await run_callable(plan.callable, arguments)
            else:
                positional, keywords = plan.callable.bind(arguments)
                value = await enter_dependency(ctx, open_dependency(*positional, **keywords))

            if self.cache:
                ctx.cache[self] = value

            return value

        return resolve


def open_dependency_for(
    factory: typing.Callable[..., typing.Any],
) -> typing.Callable[..., contextlib.AbstractAsyncContextManager[typing.Any]] | None:
    """Wrap a generator factory so the value it yields is released when the invocation ends."""

    if inspection.is_async_generator_callable(factory):
        return contextlib.asynccontextmanager(factory)

    if inspection.is_generator_callable(factory):
        open_sync_dependency = contextlib.contextmanager(factory)

        def open_in_threadpool(*args: object, **kwargs: object) -> contextlib.AbstractAsyncContextManager[typing.Any]:
            return run_context_in_threadpool(open_sync_dependency(*args, **kwargs))

        return open_in_threadpool

    return None


async def enter_dependency(
    context: InvocationContext,
    dependency: contextlib.AbstractAsyncContextManager[typing.Any],
) -> object:
    """Open a dependency that needs releasing, tying its lifetime to the invocation."""

    if context.exit_stack is None:
        raise DependencyError(
            "Cannot open a dependency that needs cleanup outside an active invocation context. "
            "Enter the context with `async with context:` before invoking."
        )

    return await context.exit_stack.enter_async_context(dependency)


@contextlib.asynccontextmanager
async def run_context_in_threadpool[T](
    manager: contextlib.AbstractContextManager[T],
) -> typing.AsyncIterator[T]:
    """Run a synchronous context manager's enter and exit off the event loop."""

    value = await run_in_threadpool(manager.__enter__)
    try:
        yield value
    except BaseException as exc:
        # forward the real exception so `except` and `finally` inside the generator behave normally
        if not await run_in_threadpool(manager.__exit__, type(exc), exc, exc.__traceback__):
            raise
    else:
        await run_in_threadpool(manager.__exit__, None, None, None)


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

    @functools.cached_property
    def positional_names(self) -> tuple[str, ...]:
        """Names of the parameters that accept a value only by position, in signature order."""

        return tuple(param.name for param in self.parameters if param.kind is inspect.Parameter.POSITIONAL_ONLY)

    def bind(self, arguments: typing.Mapping[str, object]) -> tuple[tuple[object, ...], dict[str, object]]:
        """Split resolved arguments into the positional and keyword halves this callable accepts.

        A parameter before `/` is resolved by type like any other; only the way its value is handed
        over differs. Signatures without `/` are the common case and keep the mapping unchanged.
        """

        if not self.positional_names:
            return (), dict(arguments)

        positional = tuple(arguments[name] for name in self.positional_names)
        keywords = {name: value for name, value in arguments.items() if name not in self.positional_names}
        return positional, keywords


def parse_parameter(param: inspect.Parameter) -> ParamInfo:
    default = param.default if param.default is not inspect.Parameter.empty else MISSING
    type_ = param.annotation
    metadata: tuple[typing.Any, ...] = ()

    # `Query[str] | None` carries its binding inside the union, where one unwrap cannot see it, so
    # unwrap and strip in turn: a parameter means the same thing however its optionality is spelled
    while True:
        type_, extra = inspection.unwrap_annotation(type_)
        # deeper layers come first, matching how `unwrap_annotation` orders one annotation's own metadata
        metadata = (*extra, *metadata)
        if not inspection.is_optional(type_):
            break

        type_ = inspection.strip_none(type_)
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


def inspect_callable[**PS, R](fn: typing.Callable[PS, R]) -> CallableInfo[PS, R]:
    signature = inspect.signature(fn, annotation_format=annotationlib.Format.FORWARDREF)
    return_type = signature.return_annotation
    return CallableInfo(
        callable=fn,
        parameters=tuple(parse_parameter(param) for param in signature.parameters.values()),
        return_type=MISSING if return_type is inspect.Signature.empty else return_type,
        is_async=inspection.is_async_callable(fn),
    )


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
    *,
    provided_parameter: str | None = None,
) -> CallPlan[PS, R]:
    info = inspect_callable(fn)
    if context is None:
        context = CompileContext()

    owner = inspection.callable_name(fn)
    for param in info.parameters:
        validate_parameter(param, owner)

    return CallPlan(
        callable=info,
        parameters=tuple(
            compile_parameter(context, owner, param) for param in info.parameters if param.name != provided_parameter
        ),
    )


def validate_parameter(param: ParamInfo, owner: str) -> None:
    """Reject signatures the injector can never fill, while the route is being compiled."""

    cannot_inject = f"Cannot inject parameter {param.name!r} of {owner}()."
    match param.kind:
        case inspect.Parameter.VAR_POSITIONAL:
            raise UnsupportedParameterError(
                f"{cannot_inject} The injector fills the parameters a signature declares, so *args is never filled."
            )
        case inspect.Parameter.VAR_KEYWORD:
            raise UnsupportedParameterError(
                f"{cannot_inject} The injector fills the parameters a signature declares, so **kwargs is never filled."
            )

    if param.type is MISSING and param.default is MISSING:
        raise UnannotatedParameterError(
            f"Parameter {param.name!r} of {owner}() has no type annotation. "
            f"Annotate it so the injector knows what to provide, or give it a default value."
        )


def compile_parameter(context: CompileContext, owner: str, param: ParamInfo) -> ParameterPlan:
    binding = find_binding(param, owner)
    return ParameterPlan(param=param, resolve=binding.compile(context, param))


def find_binding(param: ParamInfo, owner: str) -> Binding:
    bindings = tuple(
        candidate for candidate in param.metadata if not isinstance(candidate, type) and isinstance(candidate, Binding)
    )
    if len(bindings) > 1:
        # name the binding types rather than repr them, so a bound secret never reaches the log
        listed = ", ".join(type(binding).__name__ for binding in bindings)
        raise AmbiguousBindingError(
            f"Parameter {param.name!r} of {owner}() has {len(bindings)} bindings: {listed}. "
            f"Annotate it with exactly one."
        )

    return bindings[0] if bindings else Inject()


async def resolve_parameter(plan: ParameterPlan, context: InvocationContext) -> object:
    """Resolve one parameter, letting an override stand in for whatever binding it carries."""

    override = context.overrides.get(plan.param.annotation)
    if override is None:
        return await plan.resolve(context)

    # overrides only exist in tests, so compiling one per call costs nothing that matters
    return await override.compile(CompileContext(), plan.param)(context)


async def resolve_arguments(plan: CallPlan[..., typing.Any], context: InvocationContext) -> dict[str, object]:
    """Resolve every parameter of a plan, keyed by name and ordered as the signature declares them."""

    try:
        # overrides are a testing tool, so requests that use none keep the shorter path
        if not context.overrides:
            return {parameter.param.name: await parameter.resolve(context) for parameter in plan.parameters}

        return {parameter.param.name: await resolve_parameter(parameter, context) for parameter in plan.parameters}
    except UnresolvedDependencyError as exc:
        exc.owner = exc.owner or inspection.callable_name(plan.callable.callable)
        raise


async def run_callable(info: CallableInfo[..., typing.Any], arguments: dict[str, object]) -> object:
    """Call a callable with resolved arguments, keeping synchronous work off the event loop."""

    positional, keywords = info.bind(arguments)
    if info.is_async:
        return await info.callable(*positional, **keywords)

    return await run_in_threadpool(info.callable, *positional, **keywords)


@typing.overload
async def invoke[R](plan: CallPlan[..., typing.Awaitable[R]], context: InvocationContext) -> R: ...


@typing.overload
async def invoke[R](plan: CallPlan[..., R | typing.Awaitable[R]], context: InvocationContext) -> R: ...


async def invoke[R](plan: CallPlan[..., typing.Any], context: InvocationContext) -> R:
    arguments = await resolve_arguments(plan, context)
    return typing.cast(R, await run_callable(plan.callable, arguments))


type Injected[T] = typing.Annotated[T, Inject()]
