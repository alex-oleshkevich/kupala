import pathlib
import stat

import pytest
from dulwich import porcelain

from kupala_gen import sources
from kupala_gen.sources import BundledTemplate, FileTemplate, GitTemplate, TemplateIdentity, resolve_template


class TestFileTemplate:
    def test_snapshots_a_trusted_directory_with_a_deterministic_identity(self, tmp_path: pathlib.Path) -> None:
        source = tmp_path / "template"
        source.mkdir()
        (source / "empty").mkdir()
        executable = source / "script"
        executable.write_bytes(b"#!/bin/sh\n")
        executable.chmod(0o755)

        template = FileTemplate(source.as_uri())
        with resolve_template(template, trust=True) as first:
            identity = first.identity
            assert (first.root / "script").read_bytes() == b"#!/bin/sh\n"
            assert stat.S_IMODE((first.root / "script").stat().st_mode) == 0o755
            assert (first.root / "empty").is_dir()
            source.joinpath("script").write_text("changed")
            assert (first.root / "script").read_bytes() == b"#!/bin/sh\n"

        source.joinpath("script").write_bytes(b"#!/bin/sh\n")
        source.joinpath("script").chmod(0o755)
        with resolve_template(template, trust=True) as second:
            assert second.identity == identity

    def test_requires_an_absolute_file_uri_and_explicit_trust(self, tmp_path: pathlib.Path) -> None:
        source = tmp_path / "template"
        source.mkdir()

        with pytest.raises(ValueError, match="absolute file URI"):
            with resolve_template(FileTemplate("template"), trust=True):
                pass
        with pytest.raises(PermissionError, match="not trusted"):
            with resolve_template(FileTemplate(source.as_uri())):
                pass

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
        with pytest.raises(PermissionError, match="identity changed"):
            with resolve_template(template, expected=wrong):
                pass

    def test_rejects_symlinks_special_files_and_case_collisions(self, tmp_path: pathlib.Path) -> None:
        source = tmp_path / "template"
        source.mkdir()
        (source / "target").write_text("content")
        (source / "link").symlink_to("target")

        with pytest.raises(ValueError, match="symlink"):
            with resolve_template(FileTemplate(source.as_uri()), trust=True):
                pass

        (source / "link").unlink()
        (source / "Name").write_text("one")
        (source / "name").write_text("two")
        with pytest.raises(ValueError, match="case-colliding"):
            with resolve_template(FileTemplate(source.as_uri()), trust=True):
                pass


class TestBundledTemplate:
    def test_resolves_an_installed_package_directory_without_trust(self) -> None:
        with resolve_template(BundledTemplate("kupala_gen", "generators")) as snapshot:
            assert snapshot.identity.source == "bundled:kupala_gen/generators"
            assert (snapshot.root / "model.py").is_file()

    def test_rejects_a_missing_or_escaping_resource(self) -> None:
        with pytest.raises(ValueError, match="Unsafe bundled template path"):
            with resolve_template(BundledTemplate("kupala_gen", "../templates")):
                pass
        with pytest.raises(FileNotFoundError):
            with resolve_template(BundledTemplate("kupala_gen", "missing")):
                pass


class TestGitTemplate:
    def test_resolves_a_full_commit_without_checking_out_git_metadata(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        origin = porcelain.init(tmp_path / "origin")
        origin.path.joinpath("file.txt").write_text("content")
        porcelain.add(origin, paths=["file.txt"])
        commit = porcelain.commit(origin, message=b"template", author=b"Test <test@example.com>")
        clone = sources.porcelain.clone

        def clone_local(source: str, target: pathlib.Path, **kwargs: object):
            assert source == "https://example.test/template.git"
            assert kwargs["bare"] is True
            assert kwargs["recurse_submodules"] is False
            return clone(str(origin.path), target, **kwargs)

        monkeypatch.setattr(sources.porcelain, "clone", clone_local)
        template = GitTemplate("https://example.test/template.git", commit.decode())

        with resolve_template(template, trust=True) as snapshot:
            assert snapshot.identity.resolved == commit.decode()
            assert (snapshot.root / "file.txt").read_text() == "content"
            assert not (snapshot.root / ".git").exists()

    def test_rejects_unsafe_urls_and_noninteractive_symbolic_refs(self) -> None:
        for url in (
            "http://example.test/template.git",
            "ssh://example.test/template.git",
            "https://user:secret@example.test/template.git",
        ):
            with pytest.raises(ValueError, match="HTTPS Git URL"):
                with resolve_template(GitTemplate(url, "0" * 40), trust=True):
                    pass

        with pytest.raises(ValueError, match="full commit"):
            with resolve_template(GitTemplate("https://example.test/template.git", "main"), trust=True):
                pass
