import os
import pathlib
import stat

import pytest
from dulwich import porcelain
from dulwich.config import Config
from dulwich.objects import Blob, Tree
from dulwich.repo import MemoryRepo, Repo

from kupala_gen import sources
from kupala_gen.sources import BundledTemplate, FileTemplate, GitTemplate, TemplateIdentity, resolve_template


class TestFileTemplate:
    def test_snapshots_a_trusted_directory_with_a_deterministic_identity(self, tmp_path: pathlib.Path) -> None:
        source = tmp_path / "template"
        source.mkdir()
        (source / "empty").mkdir()
        (source / ".git").mkdir()
        (source / ".git" / "config").write_text("ignored")
        executable = source / "script"
        executable.write_bytes(b"#!/bin/sh\n")
        executable.chmod(0o755)

        template = FileTemplate(source.as_uri())
        with resolve_template(template, trust=True) as first:
            identity = first.identity
            assert (first.root / "script").read_bytes() == b"#!/bin/sh\n"
            assert stat.S_IMODE((first.root / "script").stat().st_mode) == 0o755
            assert (first.root / "empty").is_dir()
            assert not (first.root / ".git").exists()
            source.joinpath("script").write_text("changed")
            assert (first.root / "script").read_bytes() == b"#!/bin/sh\n"

        source.joinpath("script").write_bytes(b"#!/bin/sh\n")
        source.joinpath("script").chmod(0o755)
        with resolve_template(template, trust=True) as second:
            assert second.identity == identity

    def test_requires_an_absolute_file_uri_and_explicit_trust(self, tmp_path: pathlib.Path) -> None:
        source = tmp_path / "template"
        source.mkdir()

        with (
            pytest.raises(ValueError, match="absolute file URI"),
            resolve_template(FileTemplate("template"), trust=True),
        ):
            pass  # pragma: no cover
        with (
            pytest.raises(ValueError, match="absolute file URI"),
            resolve_template(FileTemplate("file:template"), trust=True),
        ):
            pass  # pragma: no cover
        with pytest.raises(PermissionError, match="not trusted"), resolve_template(FileTemplate(source.as_uri())):
            pass  # pragma: no cover

        linked = tmp_path / "linked"
        linked.symlink_to(source, target_is_directory=True)
        with (
            pytest.raises(ValueError, match="may not be a symlink"),
            resolve_template(FileTemplate(linked.as_uri()), trust=True),
        ):
            pass  # pragma: no cover

    def test_accepts_an_exact_recorded_identity(self, tmp_path: pathlib.Path) -> None:
        source = tmp_path / "template"
        source.mkdir()
        (source / "file.txt").write_text("content")
        template = FileTemplate(source.as_uri())

        with resolve_template(template, trust=True) as snapshot:
            expected = snapshot.identity
        with resolve_template(template, expected=expected):
            pass

        wrong = TemplateIdentity(expected.source, expected.revision, "0" * 64)
        with pytest.raises(PermissionError, match="identity changed"), resolve_template(template, expected=wrong):
            pass  # pragma: no cover

        approved: list[TemplateIdentity] = []

        def approve(identity: TemplateIdentity) -> bool:
            approved.append(identity)
            return True

        with resolve_template(template, confirm=approve) as snapshot:
            assert approved == [snapshot.identity]
        with (
            pytest.raises(PermissionError, match="not trusted"),
            resolve_template(template, confirm=lambda identity: False),
        ):
            pass  # pragma: no cover

    def test_rejects_symlinks_special_files_and_case_collisions(self, tmp_path: pathlib.Path) -> None:
        source = tmp_path / "template"
        source.mkdir()
        (source / "target").write_text("content")
        (source / "link").symlink_to("target")

        with pytest.raises(ValueError, match="symlink"), resolve_template(FileTemplate(source.as_uri()), trust=True):
            pass  # pragma: no cover

        (source / "link").unlink()
        (source / "Name").write_text("one")
        (source / "name").write_text("two")
        with (
            pytest.raises(ValueError, match="case-colliding"),
            resolve_template(FileTemplate(source.as_uri()), trust=True),
        ):
            pass  # pragma: no cover

        (source / "Name").unlink()
        (source / "name").unlink()
        os.mkfifo(source / "pipe")
        with (
            pytest.raises(ValueError, match="special file"),
            resolve_template(FileTemplate(source.as_uri()), trust=True),
        ):
            pass  # pragma: no cover


class TestBundledTemplate:
    def test_resolves_an_installed_package_directory_without_trust(self) -> None:
        with resolve_template(BundledTemplate("kupala_gen", "generators")) as snapshot:
            assert snapshot.identity.source == "bundled:kupala_gen/generators"
            assert (snapshot.root / "model.py").is_file()

    def test_rejects_a_missing_or_escaping_resource(self) -> None:
        with (
            pytest.raises(ValueError, match="Unsafe bundled template path"),
            resolve_template(BundledTemplate("kupala_gen", "../templates")),
        ):
            pass  # pragma: no cover
        with pytest.raises(FileNotFoundError), resolve_template(BundledTemplate("kupala_gen", "missing")):
            pass  # pragma: no cover


class TestGitTemplate:
    def test_resolves_a_full_commit_without_checking_out_git_metadata(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        origin = porcelain.init(tmp_path / "origin")
        origin_path = pathlib.Path(origin.path)
        origin_path.joinpath("nested").mkdir()
        origin_path.joinpath("file.txt").write_text("content")
        origin_path.joinpath("nested", "script").write_text("script")
        origin_path.joinpath("nested", "script").chmod(0o755)
        porcelain.add(origin, paths=["file.txt", "nested/script"])
        commit = porcelain.commit(origin, message=b"template", author=b"Test <test@example.com>")
        clone = sources.porcelain.clone

        def clone_local(
            source: str,
            target: pathlib.Path,
            *,
            bare: bool,
            checkout: bool,
            origin: str | None,
            config: Config,
            recurse_submodules: bool,
        ) -> Repo:
            assert source == "https://example.test/template.git"
            assert bare is True
            assert recurse_submodules is False
            return clone(
                str(origin_path),
                target,
                bare=bare,
                checkout=checkout,
                origin=origin,
                config=config,
                recurse_submodules=recurse_submodules,
            )

        monkeypatch.setattr(sources.porcelain, "clone", clone_local)
        template = GitTemplate("https://example.test/template.git", commit.decode())

        with resolve_template(template, trust=True) as snapshot:
            assert snapshot.identity.resolved == commit.decode()
            assert (snapshot.root / "file.txt").read_text() == "content"
            assert (snapshot.root / "nested" / "script").read_text() == "script"
            assert not (snapshot.root / ".git").exists()

    def test_rejects_unsafe_urls_and_noninteractive_symbolic_refs(self) -> None:
        for url in (
            "http://example.test/template.git",
            "ssh://example.test/template.git",
            "https://user:secret@example.test/template.git",
            "https://example.test/template.git?token=secret",
        ):
            with (
                pytest.raises(ValueError, match="HTTPS Git URL"),
                resolve_template(GitTemplate(url, "0" * 40), trust=True),
            ):
                pass  # pragma: no cover

        with (
            pytest.raises(ValueError, match="full commit"),
            resolve_template(GitTemplate("https://example.test/template.git", "main"), trust=True),
        ):
            pass  # pragma: no cover

    def test_confirms_a_symbolic_git_ref_after_resolving_its_commit(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        origin = porcelain.init(tmp_path / "origin")
        origin_path = pathlib.Path(origin.path)
        origin_path.joinpath("file.txt").write_text("content")
        porcelain.add(origin, paths=["file.txt"])
        commit = porcelain.commit(origin, message=b"template", author=b"Test <test@example.com>")
        clone = sources.porcelain.clone

        def clone_local(
            source: str,
            target: pathlib.Path,
            *,
            bare: bool,
            checkout: bool,
            origin: str | None,
            config: Config,
            recurse_submodules: bool,
        ) -> Repo:
            return clone(
                str(origin_path),
                target,
                bare=bare,
                checkout=checkout,
                origin=origin,
                config=config,
                recurse_submodules=recurse_submodules,
            )

        monkeypatch.setattr(sources.porcelain, "clone", clone_local)
        approved: list[TemplateIdentity] = []

        def approve(identity: TemplateIdentity) -> bool:
            approved.append(identity)
            return True

        with resolve_template(GitTemplate("https://example.test/template.git", "HEAD"), confirm=approve) as snapshot:
            assert snapshot.identity.resolved == commit.decode()
            assert approved == [snapshot.identity]

    def test_rejects_unicode_normalized_local_collisions(self, tmp_path: pathlib.Path) -> None:
        source = tmp_path / "template"
        source.mkdir()
        source.joinpath("é").write_text("one")
        source.joinpath("e\N{COMBINING ACUTE ACCENT}").write_text("two")

        with (
            pytest.raises(ValueError, match="case-colliding"),
            resolve_template(FileTemplate(source.as_uri()), trust=True),
        ):
            pass  # pragma: no cover

    @pytest.mark.parametrize(
        ("case", "message"),
        [
            ("root-file", "invalid tree"),
            ("non-utf8", "non-UTF-8"),
            ("unsafe", "unsafe path"),
            ("case-collision", "case-colliding"),
            ("invalid-file", "invalid file"),
            ("symlink", "unsupported entry"),
        ],
    )
    def test_rejects_invalid_git_trees(self, tmp_path: pathlib.Path, case: str, message: str) -> None:
        repo = MemoryRepo()
        blob = Blob.from_string(b"content")
        repo.object_store.add_object(blob)
        if case == "root-file":
            tree_id = blob.id
        else:
            tree = Tree()
            if case == "non-utf8":
                tree.add(b"\xff", stat.S_IFREG | 0o644, blob.id)
            elif case == "unsafe":
                tree.add(b"..", stat.S_IFREG | 0o644, blob.id)
            elif case == "case-collision":
                tree.add(b"Name", stat.S_IFREG | 0o644, blob.id)
                tree.add(b"name", stat.S_IFREG | 0o644, blob.id)
            elif case == "invalid-file":
                child = Tree()
                repo.object_store.add_object(child)
                tree.add(b"file", stat.S_IFREG | 0o644, child.id)
            else:
                tree.add(b"link", stat.S_IFLNK, blob.id)
            repo.object_store.add_object(tree)
            tree_id = tree.id

        with pytest.raises((TypeError, ValueError), match=message):
            sources._export_tree(repo, tree_id, tmp_path / case)
