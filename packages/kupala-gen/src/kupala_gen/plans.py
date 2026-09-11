import dataclasses
import enum
import os
import pathlib
import stat
import tempfile
import typing

import click


class OperationStatus(enum.Enum):
    CREATED = "created"
    MODIFIED = "modified"
    UNCHANGED = "unchanged"
    CONFLICTED = "conflicted"
    FAILED = "failed"
    ROLLED_BACK = "rolled-back"


@dataclasses.dataclass(frozen=True, slots=True)
class CreateFile:
    path: str | pathlib.PurePath
    content: str | bytes
    mode: int = 0o644
    overwriteable: bool = False
    sensitive: bool = False


@dataclasses.dataclass(frozen=True, slots=True)
class ModifyFile:
    path: str | pathlib.PurePath
    before: str | bytes
    after: str | bytes
    mode: int | None = None
    sensitive: bool = False

    def render(self, content: bytes) -> str | bytes:
        return self.after


@dataclasses.dataclass(frozen=True, slots=True)
class CreateDirectory:
    path: str | pathlib.PurePath
    mode: int = 0o755


@typing.runtime_checkable
class FileModification(typing.Protocol):
    @property
    def path(self) -> str | pathlib.PurePath: ...

    @property
    def before(self) -> str | bytes: ...

    @property
    def mode(self) -> int | None: ...

    @property
    def sensitive(self) -> bool: ...

    def render(self, content: bytes) -> str | bytes: ...


type ChangeOperation = CreateFile | CreateDirectory | FileModification


@dataclasses.dataclass(frozen=True, slots=True)
class ChangePlan:
    operations: tuple[ChangeOperation, ...]


@dataclasses.dataclass(frozen=True, slots=True)
class PreparedOperation:
    relative_path: pathlib.PurePath
    path: pathlib.Path
    status: OperationStatus
    directory: bool
    before: bytes | None
    after: bytes | None
    before_mode: int | None
    after_mode: int
    sensitive: bool


@dataclasses.dataclass(frozen=True, slots=True)
class PreparedPlan:
    target_root: pathlib.Path
    root_device: int
    root_inode: int
    operations: tuple[PreparedOperation, ...]


@dataclasses.dataclass(frozen=True, slots=True)
class OperationResult:
    path: pathlib.PurePath
    status: OperationStatus


@dataclasses.dataclass(frozen=True, slots=True)
class GenerationReport:
    operations: tuple[OperationResult, ...]


class ConflictError(click.UsageError):
    def __init__(self, message: str, path: str | pathlib.PurePath = ".") -> None:
        super().__init__(message)
        self.path = pathlib.PurePath(path)

    @property
    def report(self) -> GenerationReport:
        return GenerationReport((OperationResult(self.path, OperationStatus.CONFLICTED),))


class ApplyError(OSError):
    def __init__(self, error: BaseException, report: GenerationReport) -> None:
        super().__init__(str(error))
        self.report = report


def _bytes(content: str | bytes) -> bytes:
    return content.encode() if isinstance(content, str) else content


def _relative_path(value: str | pathlib.PurePath) -> pathlib.PurePath:
    path = pathlib.PurePath(value)
    windows_path = pathlib.PureWindowsPath(str(value))
    if (
        not path.parts
        or path == pathlib.PurePath(".")
        or path.is_absolute()
        or windows_path.is_absolute()
        or windows_path.drive
    ):
        raise ConflictError(f"Unsafe target path: {value}")
    if "\0" in str(path) or ".." in path.parts:
        raise ConflictError(f"Unsafe target path: {value}")
    return path


def _mode(path: pathlib.Path) -> int:
    return stat.S_IMODE(path.stat(follow_symlinks=False).st_mode)


def _inspect_ancestors(
    root: pathlib.Path,
    relative: pathlib.PurePath,
    planned_directories: set[pathlib.PurePath],
) -> None:
    current = root
    for part in relative.parts[:-1]:
        current /= part
        current_relative = pathlib.PurePath(*current.relative_to(root).parts)
        if current_relative in planned_directories:
            continue
        if current.is_symlink():
            raise ConflictError(f"Target path has a symlink ancestor: {relative}")
        if current.exists() and not current.is_dir():
            raise ConflictError(f"Target path has a non-directory ancestor: {relative}")
        if not current.exists():
            raise ConflictError(f"Target directory does not exist: {current_relative}")


def _check_existing_case(root: pathlib.Path, relative: pathlib.PurePath) -> None:
    current = root
    for part in relative.parts:
        if not current.is_dir():
            return
        if any(child.name.casefold() == part.casefold() and child.name != part for child in current.iterdir()):
            raise ConflictError(f"Target path case-collides with an existing path: {relative}")
        current /= part


def _check_collisions(operations: tuple[ChangeOperation, ...]) -> None:
    paths: list[tuple[pathlib.PurePath, tuple[str, ...], bool]] = []
    for operation in operations:
        try:
            path = _relative_path(operation.path)
        except ConflictError as error:
            error.path = pathlib.PurePath(operation.path)
            raise
        folded = tuple(part.casefold() for part in path.parts)
        directory = isinstance(operation, CreateDirectory)
        for previous, previous_folded, previous_directory in paths:
            if folded == previous_folded:
                raise ConflictError(f"Duplicate or case-colliding target path: {path}", path)
            if folded[: len(previous_folded)] == previous_folded and not previous_directory:
                raise ConflictError(f"File-directory conflict: {previous} and {path}", path)
            if previous_folded[: len(folded)] == folded:
                raise ConflictError(f"Operations are out of order or conflict: {path} and {previous}", path)
        paths.append((path, folded, directory))


def _prepare_operation(
    operation: ChangeOperation,
    root: pathlib.Path,
    planned_directories: set[pathlib.PurePath],
    *,
    force: bool,
) -> PreparedOperation:
    relative = _relative_path(operation.path)
    target = root / relative
    _inspect_ancestors(root, relative, planned_directories)
    _check_existing_case(root, relative)
    if target.is_symlink():
        raise ConflictError(f"Target path is a symlink: {relative}")

    exists = target.exists()
    if isinstance(operation, CreateDirectory):
        if exists and not target.is_dir():
            raise ConflictError(f"A file already exists at directory target: {relative}")
        before_mode = _mode(target) if exists else None
        status = (
            OperationStatus.UNCHANGED
            if before_mode == operation.mode
            else OperationStatus.MODIFIED
            if exists
            else OperationStatus.CREATED
        )
        return PreparedOperation(relative, target, status, True, None, None, before_mode, operation.mode, False)

    if exists and not target.is_file():
        raise ConflictError(f"Unsupported target file type: {relative}")

    if isinstance(operation, FileModification):
        if not exists:
            raise ConflictError(f"File does not exist: {relative}")
        actual = target.read_bytes()
        expected = _bytes(operation.before)
        if actual != expected:
            raise ConflictError(f"File changed since it was planned: {relative}")
        after = _bytes(operation.render(actual))
        before_mode = _mode(target)
        after_mode = operation.mode if operation.mode is not None else before_mode
        status = (
            OperationStatus.UNCHANGED if actual == after and before_mode == after_mode else OperationStatus.MODIFIED
        )
        return PreparedOperation(
            relative,
            target,
            status,
            False,
            actual,
            after,
            before_mode,
            after_mode,
            operation.sensitive,
        )

    after = _bytes(operation.content)
    if not exists:
        return PreparedOperation(
            relative,
            target,
            OperationStatus.CREATED,
            False,
            None,
            after,
            None,
            operation.mode,
            operation.sensitive,
        )

    actual = target.read_bytes()
    before_mode = _mode(target)
    if actual != after and not (force and operation.overwriteable):
        raise ConflictError(f"File already exists with different content: {relative}")
    status = (
        OperationStatus.UNCHANGED if actual == after and before_mode == operation.mode else OperationStatus.MODIFIED
    )
    return PreparedOperation(
        relative,
        target,
        status,
        False,
        actual,
        after,
        before_mode,
        operation.mode,
        operation.sensitive,
    )


def prepare_plan(
    plan: ChangePlan,
    target_root: pathlib.Path,
    *,
    force: bool = False,
) -> PreparedPlan:
    root = target_root.resolve()
    if not root.is_dir():
        raise ConflictError(f"Target root is not a directory: {target_root}")
    root_stat = root.stat(follow_symlinks=False)

    _check_collisions(plan.operations)
    prepared: list[PreparedOperation] = []
    planned_directories: set[pathlib.PurePath] = set()
    for operation in plan.operations:
        try:
            item = _prepare_operation(operation, root, planned_directories, force=force)
        except ConflictError as error:
            error.path = pathlib.PurePath(operation.path)
            raise
        prepared.append(item)
        if item.directory:
            planned_directories.add(item.relative_path)
    return PreparedPlan(root, root_stat.st_dev, root_stat.st_ino, tuple(prepared))


def _matches(operation: PreparedOperation, *, after: bool) -> bool:
    if operation.path.is_symlink() or not operation.path.exists():
        return False
    expected_mode = operation.after_mode if after else operation.before_mode
    if _mode(operation.path) != expected_mode:
        return False
    if operation.directory:
        return operation.path.is_dir()
    expected = operation.after if after else operation.before
    return operation.path.is_file() and operation.path.read_bytes() == expected


def _recheck(operation: PreparedOperation, root: pathlib.Path) -> None:
    _inspect_ancestors(root, operation.relative_path, set())
    if operation.status is OperationStatus.CREATED:
        if operation.path.exists() or operation.path.is_symlink():
            raise ConflictError(f"Target appeared after preflight: {operation.relative_path}", operation.relative_path)
    elif not _matches(operation, after=False):
        raise ConflictError(f"Target changed after preflight: {operation.relative_path}", operation.relative_path)


def _backup_path(operation: PreparedOperation) -> pathlib.Path:
    descriptor, name = tempfile.mkstemp(prefix=f".{operation.path.name}.kupala-backup-", dir=operation.path.parent)
    os.close(descriptor)
    backup = pathlib.Path(name)
    backup.write_bytes(typing.cast(bytes, operation.before))
    backup.chmod(typing.cast(int, operation.before_mode))
    return backup


def _write_file(operation: PreparedOperation) -> pathlib.Path | None:
    backup = _backup_path(operation) if operation.status is OperationStatus.MODIFIED else None
    descriptor, name = tempfile.mkstemp(prefix=f".{operation.path.name}.kupala-", dir=operation.path.parent)
    temporary = pathlib.Path(name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(typing.cast(bytes, operation.after))
        temporary.chmod(operation.after_mode)
        os.replace(temporary, operation.path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        if backup is not None:
            backup.unlink(missing_ok=True)
        raise
    return backup


def _root_matches(plan: PreparedPlan) -> bool:
    try:
        current = plan.target_root.stat(follow_symlinks=False)
    except OSError:
        return False
    return stat.S_ISDIR(current.st_mode) and current.st_dev == plan.root_device and current.st_ino == plan.root_inode


def _check_root(plan: PreparedPlan) -> None:
    if not _root_matches(plan):
        raise ConflictError("Target root changed after preflight")


def _rollback(
    operation: PreparedOperation,
    backup: pathlib.Path | None,
    root: pathlib.Path,
) -> bool:
    _inspect_ancestors(root, operation.relative_path, set())
    if operation.status is OperationStatus.CREATED:
        if _matches(operation, after=True):
            operation.path.rmdir() if operation.directory else operation.path.unlink()
            return True
        return False
    if not _matches(operation, after=True):
        return False
    if operation.directory:
        operation.path.chmod(typing.cast(int, operation.before_mode))
    else:
        os.replace(typing.cast(pathlib.Path, backup), operation.path)
    return True


def apply_plan(plan: PreparedPlan) -> GenerationReport:
    completed: list[tuple[PreparedOperation, pathlib.Path | None]] = []
    statuses: dict[pathlib.PurePath, OperationStatus] = {}
    current: PreparedOperation | None = None
    try:
        for operation in plan.operations:
            if operation.status is OperationStatus.UNCHANGED:
                statuses[operation.relative_path] = OperationStatus.UNCHANGED
                continue
            current = operation
            _check_root(plan)
            _recheck(operation, plan.target_root)
            if operation.directory:
                if operation.status is OperationStatus.CREATED:
                    operation.path.mkdir(mode=operation.after_mode)
                    try:
                        operation.path.chmod(operation.after_mode)
                    except BaseException:
                        operation.path.rmdir()
                        raise
                else:
                    operation.path.chmod(operation.after_mode)
                backup = None
            else:
                backup = _write_file(operation)
            completed.append((operation, backup))
            statuses[operation.relative_path] = operation.status
            current = None
    except BaseException as error:
        if isinstance(error, ConflictError) and not completed:
            raise
        if not _root_matches(plan):
            error.add_note("Could not roll back because the target root changed.")
        else:
            for operation, backup in reversed(completed):
                try:
                    _check_root(plan)
                    if _rollback(operation, backup, plan.target_root):
                        statuses[operation.relative_path] = OperationStatus.ROLLED_BACK
                    else:
                        recovery = f" Backup preserved as {backup.name}." if backup is not None else ""
                        error.add_note(f"Could not roll back {operation.relative_path}.{recovery}")
                except Exception:  # noqa: BLE001 - rollback must preserve the original apply error
                    error.add_note(f"Could not roll back {operation.relative_path}; recovery files were preserved.")
        statuses[typing.cast(PreparedOperation, current).relative_path] = OperationStatus.FAILED
        report = GenerationReport(
            tuple(
                OperationResult(operation.relative_path, statuses[operation.relative_path])
                for operation in plan.operations
                if operation.relative_path in statuses
            )
        )
        if not isinstance(error, Exception):
            raise
        failure = ApplyError(error, report)
        for note in getattr(error, "__notes__", ()):
            failure.add_note(note)
        raise failure from None

    for _, backup in completed:
        if backup is not None:
            backup.unlink(missing_ok=True)
    return GenerationReport(
        tuple(OperationResult(operation.relative_path, operation.status) for operation in plan.operations)
    )
