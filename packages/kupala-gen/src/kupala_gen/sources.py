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
from dulwich.objects import Blob, Tree
from dulwich.objectspec import parse_commit
from dulwich.repo import BaseRepo


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
    if not path.parts or path.is_absolute() or "." in path.parts or ".." in path.parts:
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


def _git_url(value: str) -> str:
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


def _copy_directory(source: pathlib.Path, destination: pathlib.Path) -> str:
    if source.is_symlink():
        raise ValueError("Template source may not be a symlink.")
    if not source.is_dir():
        raise FileNotFoundError(source)
    digest = hashlib.sha256()
    destination.mkdir()

    def record(kind: bytes, relative: pathlib.PurePath, mode: int, content: bytes = b"") -> None:
        path = os.fsencode(relative.as_posix())
        digest.update(kind)
        digest.update(len(path).to_bytes(4))
        digest.update(path)
        digest.update(mode.to_bytes(2))
        digest.update(len(content).to_bytes(8))
        digest.update(content)

    def copy(current: pathlib.Path, relative: pathlib.PurePath) -> None:
        entries = sorted(os.scandir(current), key=lambda entry: os.fsencode(entry.name))
        folded: set[str] = set()
        for entry in entries:
            if entry.name == ".git":
                continue
            name = unicodedata.normalize("NFC", entry.name).casefold()
            if name in folded:
                raise ValueError(f"Template contains case-colliding paths: {relative / entry.name}")
            folded.add(name)
            path = pathlib.Path(entry.path)
            target_relative = relative / entry.name
            target = destination / target_relative
            info = entry.stat(follow_symlinks=False)
            if stat.S_ISLNK(info.st_mode):
                raise ValueError(f"Template contains a symlink: {target_relative}")
            if stat.S_ISDIR(info.st_mode):
                target.mkdir(mode=0o755)
                record(b"d", target_relative, 0o755)
                copy(path, target_relative)
                continue
            if not stat.S_ISREG(info.st_mode):
                raise ValueError(f"Template contains a special file: {target_relative}")
            content = path.read_bytes()
            mode = 0o755 if info.st_mode & 0o111 else 0o644
            target.write_bytes(content)
            target.chmod(mode)
            record(b"f", target_relative, mode, content)

    copy(source, pathlib.PurePath())
    return digest.hexdigest()


def _export_tree(repo: BaseRepo, tree_id: bytes, destination: pathlib.Path) -> None:
    destination.mkdir()

    def export(tree_id: bytes, relative: pathlib.PurePath) -> None:
        tree = repo[tree_id]
        if not isinstance(tree, Tree):
            raise TypeError("Git template contains an invalid tree.")
        folded: set[str] = set()
        for entry in tree.iteritems(name_order=True):
            try:
                name = entry.path.decode()
            except UnicodeDecodeError as error:
                raise ValueError("Git template contains a non-UTF-8 path.") from error
            if not name or "/" in name or "\0" in name or name in {".", ".."}:
                raise ValueError("Git template contains an unsafe path.")
            folded_name = unicodedata.normalize("NFC", name).casefold()
            if folded_name in folded:
                raise ValueError(f"Template contains case-colliding paths: {relative / name}")
            folded.add(folded_name)
            target_relative = relative / name
            target = destination / target_relative
            if stat.S_ISDIR(entry.mode):
                target.mkdir(mode=0o755)
                export(entry.sha, target_relative)
            elif stat.S_ISREG(entry.mode):
                blob = repo[entry.sha]
                if not isinstance(blob, Blob):
                    raise ValueError("Git template contains an invalid file.")
                target.write_bytes(blob.data)
                target.chmod(0o755 if entry.mode & 0o111 else 0o644)
            else:
                raise ValueError(f"Git template contains an unsupported entry: {target_relative}")

    export(tree_id, pathlib.PurePath())


def _approve(
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
                digest = _copy_directory(local, snapshot_root)
            identity = TemplateIdentity(f"bundled:{source.package}/{resource_path}", None, digest)
        elif isinstance(source, FileTemplate):
            path = _file_path(source.url)
            digest = _copy_directory(path, snapshot_root)
            identity = TemplateIdentity(path.resolve().as_uri(), None, digest)
            _approve(identity, trust=trust, expected=expected, confirm=confirm)
        else:
            url = _git_url(source.url)
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
                _export_tree(repo, commit.tree, snapshot_root)
            finally:
                repo.close()
            identity = TemplateIdentity(url, source.revision, commit.id.decode())
            _approve(identity, trust=trust, expected=expected, confirm=confirm)
        yield TemplateSnapshot(identity, snapshot_root)
