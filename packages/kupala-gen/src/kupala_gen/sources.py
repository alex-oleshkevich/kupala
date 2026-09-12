import contextlib
import dataclasses
import hashlib
import importlib.resources
import os
import pathlib
import re
import stat
import tempfile
import typing
import unicodedata
import urllib.parse
import urllib.request

from dulwich import porcelain
from dulwich.config import ConfigDict
from dulwich.index import build_index_from_tree
from dulwich.object_store import iter_tree_contents
from dulwich.objectspec import parse_commit


@dataclasses.dataclass(frozen=True, slots=True)
class BundledTemplate:
    package: str
    path: str


@dataclasses.dataclass(frozen=True, slots=True)
class GitTemplate:
    url: str
    revision: str


@dataclasses.dataclass(frozen=True, slots=True)
class FileTemplate:
    url: str


type TemplateSource = BundledTemplate | GitTemplate | FileTemplate


@dataclasses.dataclass(frozen=True, slots=True)
class TemplateIdentity:
    source: str
    revision: str | None
    resolved: str


@dataclasses.dataclass(frozen=True, slots=True)
class TemplateSnapshot:
    identity: TemplateIdentity
    root: pathlib.Path


def _resource_path(value: str) -> pathlib.PurePosixPath:
    path = pathlib.PurePosixPath(value)
    if not path.parts or path.is_absolute() or ".." in path.parts:
        raise ValueError(f"Unsafe bundled template path: {value}")

    return path


def _file_path(value: str) -> pathlib.Path:
    parsed = urllib.parse.urlsplit(value)
    if parsed.scheme != "file" or parsed.netloc or parsed.query or parsed.fragment:
        raise ValueError("Template source must be an absolute file URI.")

    path = pathlib.Path(urllib.request.url2pathname(urllib.parse.unquote(parsed.path)))
    if not path.is_absolute():
        raise ValueError("Template source must be an absolute file URI.")

    return path


def _validate_git_url(value: str) -> str:
    parsed = urllib.parse.urlsplit(value)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("Template source must be an HTTPS Git URL without embedded credentials.")

    try:
        port = parsed.port
    except ValueError as error:
        raise ValueError("Template source must be a valid HTTPS Git URL.") from error
    host = parsed.hostname.encode("idna").decode().lower()
    if ":" in host:
        host = f"[{host}]"

    netloc = host if port in {None, 443} else f"{host}:{port}"
    return urllib.parse.urlunsplit(("https", netloc, parsed.path or "/", "", ""))


def _full_commit(value: str) -> bool:
    return len(value) in {40, 64} and re.fullmatch(r"[0-9a-fA-F]+", value) is not None


def _raise_walk_error(error: OSError) -> typing.Never:
    raise error


def _snapshot_directory(source: pathlib.Path, destination: pathlib.Path) -> str:
    if source.is_symlink():
        raise ValueError("Template source may not be a symlink.")

    if not source.is_dir():
        raise FileNotFoundError(source)

    digest = hashlib.sha256()
    destination.mkdir()
    seen: set[tuple[str, ...]] = set()
    paths: list[pathlib.Path] = []
    for root, directories, files in source.walk(on_error=_raise_walk_error):
        directories[:] = [name for name in directories if name != ".git"]
        paths.extend(root / name for name in (*directories, *files) if name != ".git")

    paths.sort(key=lambda path: tuple(os.fsencode(part) for part in path.relative_to(source).parts))

    for path in paths:
        relative = path.relative_to(source)
        key = tuple(unicodedata.normalize("NFC", part).casefold() for part in relative.parts)
        if key in seen:
            raise ValueError(f"Template contains case-colliding paths: {relative}")

        seen.add(key)

        info = path.lstat()
        if stat.S_ISLNK(info.st_mode):
            raise ValueError(f"Template contains a symlink: {relative}")

        target = destination / relative
        if stat.S_ISDIR(info.st_mode):
            kind, mode, content = b"d", 0o755, b""
            target.mkdir(mode=mode)
        elif stat.S_ISREG(info.st_mode):
            kind = b"f"
            mode = 0o755 if info.st_mode & 0o111 else 0o644
            content = path.read_bytes()
            target.write_bytes(content)
            target.chmod(mode)
        else:
            raise ValueError(f"Template contains a special file: {relative}")

        encoded = os.fsencode(relative.as_posix())
        digest.update(kind)
        digest.update(len(encoded).to_bytes(4))
        digest.update(encoded)
        digest.update(mode.to_bytes(2))
        digest.update(len(content).to_bytes(8))
        digest.update(content)

    return digest.hexdigest()


def _check_trust(
    identity: TemplateIdentity,
    *,
    trust: bool,
    expected: TemplateIdentity | None,
    confirm: typing.Callable[[TemplateIdentity], bool] | None,
) -> None:
    if expected is not None:
        if identity != expected:
            raise PermissionError("Template identity changed from the trusted value.")

        return

    if trust or (confirm is not None and confirm(identity)):
        return

    raise PermissionError("Template source is not trusted.")


@contextlib.contextmanager
def resolve_template(
    source: TemplateSource,
    *,
    trust: bool = False,
    expected: TemplateIdentity | None = None,
    confirm: typing.Callable[[TemplateIdentity], bool] | None = None,
) -> typing.Iterator[TemplateSnapshot]:
    with tempfile.TemporaryDirectory(prefix="kupala-template-") as temporary:
        snapshot_root = pathlib.Path(temporary) / "snapshot"
        if isinstance(source, BundledTemplate):
            resource_path = _resource_path(source.path)
            resource = importlib.resources.files(source.package).joinpath(*resource_path.parts)
            with importlib.resources.as_file(resource) as local:
                digest = _snapshot_directory(local, snapshot_root)
            identity = TemplateIdentity(f"bundled:{source.package}/{resource_path}", None, digest)
        elif isinstance(source, FileTemplate):
            path = _file_path(source.url)
            digest = _snapshot_directory(path, snapshot_root)
            identity = TemplateIdentity(path.resolve().as_uri(), None, digest)
            _check_trust(identity, trust=trust, expected=expected, confirm=confirm)
        else:
            url = _validate_git_url(source.url)
            if confirm is None and expected is None and not _full_commit(source.revision):
                raise ValueError("Non-interactive Git templates require a full commit SHA.")

            repository_path = pathlib.Path(temporary) / "repository.git"
            repo = porcelain.clone(
                url,
                repository_path,
                bare=True,
                checkout=False,
                origin=None,
                config=ConfigDict(),
                recurse_submodules=False,
            )

            try:
                commit = parse_commit(repo, source.revision)
                paths: set[str] = set()
                for entry in iter_tree_contents(repo.object_store, commit.tree):
                    if not stat.S_ISREG(entry.mode):
                        raise ValueError("Git template contains an unsupported entry.")

                    try:
                        entry_path = entry.path.decode()
                    except UnicodeDecodeError as error:
                        raise ValueError("Git template contains a non-UTF-8 path.") from error

                    key = unicodedata.normalize("NFC", entry_path).casefold()
                    if key in paths:
                        raise ValueError(f"Git template contains case-colliding paths: {entry_path}")

                    paths.add(key)

                checkout = pathlib.Path(temporary) / "checkout"
                checkout.mkdir()
                build_index_from_tree(
                    str(checkout),
                    str(pathlib.Path(temporary) / "index"),
                    repo.object_store,
                    commit.tree,
                )
                _snapshot_directory(checkout, snapshot_root)
            finally:
                repo.close()

            identity = TemplateIdentity(url, source.revision, commit.id.decode())
            _check_trust(identity, trust=trust, expected=expected, confirm=confirm)

        yield TemplateSnapshot(identity, snapshot_root)
