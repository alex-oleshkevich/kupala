import dataclasses
import os
import pathlib

import pytest

from kupala_gen import plans
from kupala_gen.plans import (
    ApplyError,
    ChangePlan,
    ConflictError,
    CreateDirectory,
    CreateFile,
    FileModification,
    ModifyFile,
    OperationStatus,
    apply_plan,
    prepare_plan,
)


class TestPreparePlan:
    def test_prepares_without_writing(self, tmp_path: pathlib.Path) -> None:
        prepared = prepare_plan(
            ChangePlan((CreateDirectory("pkg"), CreateFile("pkg/item.txt", "hello"))),
            tmp_path,
        )

        assert [operation.status for operation in prepared.operations] == [
            OperationStatus.CREATED,
            OperationStatus.CREATED,
        ]
        assert list(tmp_path.iterdir()) == []

    def test_recognizes_unchanged_content_and_mode(self, tmp_path: pathlib.Path) -> None:
        target = tmp_path / "item.txt"
        target.write_text("hello")
        target.chmod(0o640)

        prepared = prepare_plan(ChangePlan((CreateFile("item.txt", b"hello", mode=0o640),)), tmp_path)

        assert prepared.operations[0].status is OperationStatus.UNCHANGED

    def test_recognizes_an_unchanged_directory_mode(self, tmp_path: pathlib.Path) -> None:
        (tmp_path / "pkg").mkdir(mode=0o700)

        prepared = prepare_plan(ChangePlan((CreateDirectory("pkg", mode=0o700),)), tmp_path)

        assert prepared.operations[0].status is OperationStatus.UNCHANGED

    def test_modifies_an_expected_file(self, tmp_path: pathlib.Path) -> None:
        (tmp_path / "item.txt").write_text("before")

        prepared = prepare_plan(
            ChangePlan((ModifyFile("item.txt", before="before", after="after"),)),
            tmp_path,
        )

        assert prepared.operations[0].status is OperationStatus.MODIFIED

    def test_accepts_a_bounded_file_modification_protocol(self, tmp_path: pathlib.Path) -> None:
        @dataclasses.dataclass(frozen=True)
        class Uppercase:
            path: str
            before: str
            mode: int | None = None
            sensitive: bool = False

            def render(self, content: bytes) -> bytes:
                return content.upper()

        operation: FileModification = Uppercase("item.txt", "before")
        (tmp_path / "item.txt").write_text("before")

        prepared = prepare_plan(ChangePlan((operation,)), tmp_path)
        apply_plan(prepared)

        assert (tmp_path / "item.txt").read_text() == "BEFORE"

    def test_rejects_a_divergent_baseline(self, tmp_path: pathlib.Path) -> None:
        (tmp_path / "item.txt").write_text("changed")

        with pytest.raises(ConflictError, match="changed since it was planned") as caught:
            prepare_plan(
                ChangePlan((ModifyFile("item.txt", before="before", after="after"),)),
                tmp_path,
            )

        assert caught.value.report.operations[0].status is OperationStatus.CONFLICTED

    def test_force_only_applies_to_an_explicitly_overwriteable_operation(self, tmp_path: pathlib.Path) -> None:
        (tmp_path / "item.txt").write_text("existing")
        operation = CreateFile("item.txt", "replacement")

        with pytest.raises(ConflictError):
            prepare_plan(ChangePlan((operation,)), tmp_path, force=True)

        prepared = prepare_plan(
            ChangePlan((CreateFile("item.txt", "replacement", overwriteable=True),)),
            tmp_path,
            force=True,
        )
        assert prepared.operations[0].status is OperationStatus.MODIFIED

    @pytest.mark.parametrize(
        "path",
        [
            "/absolute",
            "C:\\absolute",
            "\\outside",
            "../outside",
            "a/../../outside",
            "a\\..\\outside",
            "bad\0name",
            ".",
        ],
    )
    def test_rejects_unsafe_paths(self, tmp_path: pathlib.Path, path: str) -> None:
        with pytest.raises(ConflictError):
            prepare_plan(ChangePlan((CreateFile(path, "content"),)), tmp_path)

    def test_rejects_symlink_destinations_and_ancestors(self, tmp_path: pathlib.Path) -> None:
        outside = tmp_path / "outside"
        outside.mkdir()
        (tmp_path / "link").symlink_to(outside, target_is_directory=True)

        for path in ("link", "link/item.txt"):
            with pytest.raises(ConflictError, match="symlink"):
                prepare_plan(ChangePlan((CreateFile(path, "content"),)), tmp_path)

    @pytest.mark.parametrize(
        "operations",
        [
            (CreateFile("item", "a"), CreateFile("item", "b")),
            (CreateFile("Item", "a"), CreateFile("item", "b")),
            (CreateFile("é", "a"), CreateFile("e\N{COMBINING ACUTE ACCENT}", "b")),
            (CreateFile("pkg", "a"), CreateFile("pkg/item", "b")),
        ],
    )
    def test_rejects_plan_collisions(self, tmp_path: pathlib.Path, operations: tuple[CreateFile, CreateFile]) -> None:
        with pytest.raises(ConflictError):
            prepare_plan(ChangePlan(operations), tmp_path)

    def test_rejects_existing_file_directory_conflicts(self, tmp_path: pathlib.Path) -> None:
        (tmp_path / "pkg").write_text("file")

        with pytest.raises(ConflictError):
            prepare_plan(ChangePlan((CreateDirectory("pkg"),)), tmp_path)

    def test_rejects_missing_and_non_directory_ancestors(self, tmp_path: pathlib.Path) -> None:
        with pytest.raises(ConflictError, match="does not exist"):
            prepare_plan(ChangePlan((CreateFile("missing/item.txt", "content"),)), tmp_path)

        (tmp_path / "file").write_text("content")
        with pytest.raises(ConflictError, match="non-directory"):
            prepare_plan(ChangePlan((CreateFile("file/item.txt", "content"),)), tmp_path)

    def test_rejects_a_directory_planned_after_its_child(self, tmp_path: pathlib.Path) -> None:
        with pytest.raises(ConflictError, match="out of order"):
            prepare_plan(
                ChangePlan((CreateFile("pkg/item.txt", "content"), CreateDirectory("pkg"))),
                tmp_path,
            )

    def test_rejects_case_collisions_in_ancestor_components(self, tmp_path: pathlib.Path) -> None:
        with pytest.raises(ConflictError):
            prepare_plan(
                ChangePlan(
                    (
                        CreateDirectory("Package"),
                        CreateFile("package/item.txt", "content"),
                    )
                ),
                tmp_path,
            )

    def test_rejects_a_case_collision_with_an_existing_path(self, tmp_path: pathlib.Path) -> None:
        (tmp_path / "Item.txt").write_text("existing")

        with pytest.raises(ConflictError, match="case-collides"):
            prepare_plan(ChangePlan((CreateFile("item.txt", "content"),)), tmp_path)

    def test_rejects_a_missing_target_root(self, tmp_path: pathlib.Path) -> None:
        with pytest.raises(ConflictError, match="not a directory"):
            prepare_plan(ChangePlan(()), tmp_path / "missing")

    def test_rejects_a_missing_modify_target(self, tmp_path: pathlib.Path) -> None:
        with pytest.raises(ConflictError, match="does not exist"):
            prepare_plan(ChangePlan((ModifyFile("item.txt", before="before", after="after"),)), tmp_path)

    def test_rejects_special_files(self, tmp_path: pathlib.Path) -> None:
        target = tmp_path / "pipe"
        os.mkfifo(target)

        with pytest.raises(ConflictError, match="Unsupported"):
            prepare_plan(ChangePlan((CreateFile("pipe", "content"),)), tmp_path)


class TestApplyPlan:
    def test_applies_files_and_directories_in_order(self, tmp_path: pathlib.Path) -> None:
        prepared = prepare_plan(
            ChangePlan((CreateDirectory("pkg", mode=0o750), CreateFile("pkg/item.txt", "hello"))),
            tmp_path,
        )

        report = apply_plan(prepared)

        assert (tmp_path / "pkg/item.txt").read_text() == "hello"
        assert os.stat(tmp_path / "pkg").st_mode & 0o777 == 0o750
        assert [result.status for result in report.operations] == [
            OperationStatus.CREATED,
            OperationStatus.CREATED,
        ]

    def test_rechecks_the_baseline_before_writing(self, tmp_path: pathlib.Path) -> None:
        target = tmp_path / "item.txt"
        target.write_text("before")
        prepared = prepare_plan(
            ChangePlan((ModifyFile("item.txt", before="before", after="after"),)),
            tmp_path,
        )
        target.write_text("concurrent")

        with pytest.raises(ConflictError, match="changed after preflight"):
            apply_plan(prepared)

        assert target.read_text() == "concurrent"

    def test_rejects_a_target_that_appears_after_preflight(self, tmp_path: pathlib.Path) -> None:
        prepared = prepare_plan(ChangePlan((CreateFile("item.txt", "content"),)), tmp_path)
        (tmp_path / "item.txt").write_text("concurrent")

        with pytest.raises(ConflictError, match="appeared after preflight"):
            apply_plan(prepared)

    def test_rejects_a_target_root_replaced_by_a_symlink(self, tmp_path: pathlib.Path) -> None:
        root = tmp_path / "root"
        moved = tmp_path / "moved"
        outside = tmp_path / "outside"
        root.mkdir()
        outside.mkdir()
        prepared = prepare_plan(ChangePlan((CreateFile("item.txt", "content"),)), root)
        root.rename(moved)
        root.symlink_to(outside, target_is_directory=True)

        with pytest.raises(ConflictError, match="root changed"):
            apply_plan(prepared)

        assert list(outside.iterdir()) == []

    def test_rejects_a_target_root_that_disappears(self, tmp_path: pathlib.Path) -> None:
        root = tmp_path / "root"
        root.mkdir()
        prepared = prepare_plan(ChangePlan((CreateFile("item.txt", "content"),)), root)
        root.rename(tmp_path / "moved")

        with pytest.raises(ConflictError, match="root changed"):
            apply_plan(prepared)

    def test_rejects_a_deleted_or_repermissioned_baseline(self, tmp_path: pathlib.Path) -> None:
        target = tmp_path / "item.txt"
        target.write_text("before")
        prepared = prepare_plan(
            ChangePlan((ModifyFile("item.txt", before="before", after="after"),)),
            tmp_path,
        )

        target.unlink()
        with pytest.raises(ConflictError, match="changed after preflight"):
            apply_plan(prepared)

        target.write_text("before")
        prepared = prepare_plan(
            ChangePlan((ModifyFile("item.txt", before="before", after="after"),)),
            tmp_path,
        )
        target.chmod(0o600)
        with pytest.raises(ConflictError, match="changed after preflight"):
            apply_plan(prepared)

    def test_applies_and_cleans_up_a_file_backup(self, tmp_path: pathlib.Path) -> None:
        target = tmp_path / "item.txt"
        target.write_text("before")
        prepared = prepare_plan(
            ChangePlan((ModifyFile("item.txt", before="before", after="after", mode=0o600),)),
            tmp_path,
        )

        apply_plan(prepared)

        assert target.read_text() == "after"
        assert os.stat(target).st_mode & 0o777 == 0o600
        assert list(tmp_path.iterdir()) == [target]

    def test_applies_an_existing_directory_mode(self, tmp_path: pathlib.Path) -> None:
        target = tmp_path / "pkg"
        target.mkdir(mode=0o700)
        prepared = prepare_plan(ChangePlan((CreateDirectory("pkg", mode=0o750),)), tmp_path)

        apply_plan(prepared)

        assert os.stat(target).st_mode & 0o777 == 0o750

    def test_skips_unchanged_operations(self, tmp_path: pathlib.Path) -> None:
        target = tmp_path / "item.txt"
        target.write_text("content")
        prepared = prepare_plan(ChangePlan((CreateFile("item.txt", "content"),)), tmp_path)

        report = apply_plan(prepared)

        assert report.operations[0].status is OperationStatus.UNCHANGED

    def test_rolls_back_completed_operations(self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
        prepared = prepare_plan(
            ChangePlan((CreateFile("first.txt", "first"), CreateFile("second.txt", "second"))),
            tmp_path,
        )
        write = plans._write_file

        def fail_second(operation: plans.PreparedOperation) -> pathlib.Path | None:
            if operation.path.name == "second.txt":
                raise OSError("disk full")
            return write(operation)

        monkeypatch.setattr(plans, "_write_file", fail_second)

        with pytest.raises(OSError, match="disk full"):
            apply_plan(prepared)

        assert list(tmp_path.iterdir()) == []

    def test_reports_a_conflict_found_after_an_earlier_write(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        prepared = prepare_plan(
            ChangePlan((CreateFile("first.txt", "first"), CreateFile("second.txt", "second"))),
            tmp_path,
        )
        write = plans._write_file

        def create_conflict(operation: plans.PreparedOperation) -> pathlib.Path | None:
            backup = write(operation)
            assert operation.path.name == "first.txt"
            (tmp_path / "second.txt").write_text("concurrent")
            return backup

        monkeypatch.setattr(plans, "_write_file", create_conflict)

        with pytest.raises(ApplyError) as caught:
            apply_plan(prepared)

        assert [result.status for result in caught.value.report.operations] == [
            OperationStatus.ROLLED_BACK,
            OperationStatus.CONFLICTED,
        ]

    def test_rolls_back_before_propagating_an_interrupt(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        prepared = prepare_plan(
            ChangePlan((CreateFile("first.txt", "first"), CreateFile("second.txt", "second"))),
            tmp_path,
        )
        write = plans._write_file

        def interrupt_second(operation: plans.PreparedOperation) -> pathlib.Path | None:
            if operation.path.name == "second.txt":
                raise KeyboardInterrupt
            return write(operation)

        monkeypatch.setattr(plans, "_write_file", interrupt_second)

        with pytest.raises(KeyboardInterrupt):
            apply_plan(prepared)

        assert list(tmp_path.iterdir()) == []

    def test_removes_a_directory_when_setting_its_mode_fails(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        prepared = prepare_plan(ChangePlan((CreateDirectory("pkg"),)), tmp_path)

        def fail_generated_directory(path: pathlib.Path, mode: int) -> None:
            assert path == tmp_path / "pkg"
            assert mode == 0o755
            raise OSError("chmod failed")

        monkeypatch.setattr(pathlib.Path, "chmod", fail_generated_directory)

        with pytest.raises(OSError, match="chmod failed"):
            apply_plan(prepared)

        assert list(tmp_path.iterdir()) == []

    def test_preserves_a_directory_setup_error_when_cleanup_fails(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        prepared = prepare_plan(ChangePlan((CreateDirectory("pkg"),)), tmp_path)
        monkeypatch.setattr(pathlib.Path, "chmod", lambda path, mode: (_ for _ in ()).throw(OSError("chmod failed")))
        monkeypatch.setattr(pathlib.Path, "rmdir", lambda path: (_ for _ in ()).throw(OSError("cleanup failed")))

        with pytest.raises(ApplyError, match="chmod failed") as caught:
            apply_plan(prepared)

        assert caught.value.__notes__ == ["Could not remove pkg after its setup failed."]

    def test_rolls_back_a_modified_file(self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
        target = tmp_path / "first.txt"
        target.write_text("before")
        prepared = prepare_plan(
            ChangePlan(
                (
                    ModifyFile("first.txt", before="before", after="after"),
                    CreateFile("second.txt", "second"),
                )
            ),
            tmp_path,
        )
        write = plans._write_file

        def fail_second(operation: plans.PreparedOperation) -> pathlib.Path | None:
            if operation.path.name == "second.txt":
                raise OSError("disk full")
            return write(operation)

        monkeypatch.setattr(plans, "_write_file", fail_second)

        with pytest.raises(ApplyError, match="disk full") as caught:
            apply_plan(prepared)

        assert target.read_text() == "before"
        assert list(tmp_path.iterdir()) == [target]
        assert [result.status for result in caught.value.report.operations] == [
            OperationStatus.ROLLED_BACK,
            OperationStatus.FAILED,
        ]

    def test_unchanged_operations_do_not_interrupt_rollback(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        changed = tmp_path / "changed.txt"
        unchanged = tmp_path / "unchanged.txt"
        changed.write_text("before")
        unchanged.write_text("same")
        prepared = prepare_plan(
            ChangePlan(
                (
                    ModifyFile("changed.txt", before="before", after="after"),
                    CreateFile("unchanged.txt", "same"),
                    CreateFile("failed.txt", "failed"),
                )
            ),
            tmp_path,
        )
        write = plans._write_file

        def fail_last(operation: plans.PreparedOperation) -> pathlib.Path | None:
            if operation.path.name == "failed.txt":
                raise OSError("failed")
            return write(operation)

        monkeypatch.setattr(plans, "_write_file", fail_last)

        with pytest.raises(OSError, match="failed"):
            apply_plan(prepared)

        assert changed.read_text() == "before"
        assert unchanged.read_text() == "same"

    def test_preserves_a_backup_when_rollback_finds_a_concurrent_edit(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        target = tmp_path / "first.txt"
        target.write_text("before")
        prepared = prepare_plan(
            ChangePlan(
                (
                    ModifyFile("first.txt", before="before", after="after"),
                    CreateFile("second.txt", "second"),
                )
            ),
            tmp_path,
        )
        write = plans._write_file

        def edit_then_fail(operation: plans.PreparedOperation) -> pathlib.Path | None:
            if operation.path.name == "second.txt":
                target.write_text("concurrent")
                raise OSError("disk full")
            return write(operation)

        monkeypatch.setattr(plans, "_write_file", edit_then_fail)

        with pytest.raises(OSError, match="disk full") as caught:
            apply_plan(prepared)

        assert target.read_text() == "concurrent"
        backups = list(tmp_path.glob(".*.kupala-backup-*"))
        assert len(backups) == 1
        assert backups[0].read_text() == "before"
        assert "Backup preserved as" in caught.value.__notes__[0]

    def test_does_not_rollback_over_an_identical_concurrent_replacement(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        target = tmp_path / "first.txt"
        target.write_text("before")
        prepared = prepare_plan(
            ChangePlan(
                (
                    ModifyFile("first.txt", before="before", after="after"),
                    CreateFile("second.txt", "second"),
                )
            ),
            tmp_path,
        )
        write = plans._write_file

        def replace_then_fail(operation: plans.PreparedOperation) -> pathlib.Path | None:
            if operation.path.name == "second.txt":
                replacement = tmp_path / "replacement"
                replacement.write_text("after")
                replacement.chmod(os.stat(target).st_mode & 0o777)
                os.replace(replacement, target)
                raise OSError("disk full")
            return write(operation)

        monkeypatch.setattr(plans, "_write_file", replace_then_fail)

        with pytest.raises(ApplyError, match="disk full"):
            apply_plan(prepared)

        assert target.read_text() == "after"
        assert len(list(tmp_path.glob(".*.kupala-backup-*"))) == 1

    def test_removes_a_backup_when_creating_the_write_temporary_fails(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        target = tmp_path / "item.txt"
        target.write_text("before")
        prepared = prepare_plan(
            ChangePlan((ModifyFile("item.txt", before="before", after="after"),)),
            tmp_path,
        )
        mkstemp = plans.tempfile.mkstemp
        calls = 0

        def fail_second(*, prefix: str, dir: pathlib.Path) -> tuple[int, str]:
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("temporary failed")
            return mkstemp(prefix=prefix, dir=dir)

        monkeypatch.setattr(plans.tempfile, "mkstemp", fail_second)

        with pytest.raises(ApplyError, match="temporary failed"):
            apply_plan(prepared)

        assert target.read_text() == "before"
        assert list(tmp_path.iterdir()) == [target]

    def test_removes_an_incomplete_backup(self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
        target = tmp_path / "item.txt"
        target.write_text("before")
        prepared = prepare_plan(
            ChangePlan((ModifyFile("item.txt", before="before", after="after"),)),
            tmp_path,
        )

        def fail_backup(path: pathlib.Path, mode: int) -> None:
            assert ".kupala-backup-" in path.name
            assert mode == os.stat(target).st_mode & 0o777
            raise OSError("backup failed")

        monkeypatch.setattr(pathlib.Path, "chmod", fail_backup)

        with pytest.raises(ApplyError, match="backup failed"):
            apply_plan(prepared)

        assert target.read_text() == "before"
        assert list(tmp_path.iterdir()) == [target]

    def test_removes_temporary_files_after_a_failed_replace(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        target = tmp_path / "item.txt"
        target.write_text("before")
        prepared = prepare_plan(
            ChangePlan((ModifyFile("item.txt", before="before", after="after"),)),
            tmp_path,
        )
        monkeypatch.setattr(os, "replace", lambda source, destination: (_ for _ in ()).throw(OSError("failed")))

        with pytest.raises(OSError, match="failed"):
            apply_plan(prepared)

        assert target.read_text() == "before"
        assert list(tmp_path.iterdir()) == [target]

    def test_removes_a_created_temporary_file_after_a_failed_replace(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        prepared = prepare_plan(ChangePlan((CreateFile("item.txt", "content"),)), tmp_path)
        monkeypatch.setattr(os, "replace", lambda source, destination: (_ for _ in ()).throw(OSError("failed")))

        with pytest.raises(OSError, match="failed"):
            apply_plan(prepared)

        assert list(tmp_path.iterdir()) == []

    def test_does_not_remove_a_concurrently_edited_created_file(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        prepared = prepare_plan(
            ChangePlan((CreateFile("first.txt", "first"), CreateFile("second.txt", "second"))),
            tmp_path,
        )
        write = plans._write_file

        def edit_then_fail(operation: plans.PreparedOperation) -> pathlib.Path | None:
            if operation.path.name == "second.txt":
                (tmp_path / "first.txt").write_text("concurrent")
                raise OSError("disk full")
            return write(operation)

        monkeypatch.setattr(plans, "_write_file", edit_then_fail)

        with pytest.raises(OSError, match="disk full"):
            apply_plan(prepared)

        assert (tmp_path / "first.txt").read_text() == "concurrent"

    def test_does_not_remove_an_identical_concurrent_replacement(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        target = tmp_path / "first.txt"
        prepared = prepare_plan(
            ChangePlan((CreateFile("first.txt", "first"), CreateFile("second.txt", "second"))),
            tmp_path,
        )
        write = plans._write_file

        def replace_then_fail(operation: plans.PreparedOperation) -> pathlib.Path | None:
            if operation.path.name == "second.txt":
                replacement = tmp_path / "replacement"
                replacement.write_text("first")
                replacement.chmod(os.stat(target).st_mode & 0o777)
                os.replace(replacement, target)
                raise OSError("disk full")
            return write(operation)

        monkeypatch.setattr(plans, "_write_file", replace_then_fail)

        with pytest.raises(OSError, match="disk full"):
            apply_plan(prepared)

        assert target.read_text() == "first"

    def test_rolls_back_a_directory_mode_change(self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
        target = tmp_path / "pkg"
        target.mkdir(mode=0o700)
        prepared = prepare_plan(
            ChangePlan((CreateDirectory("pkg", mode=0o750), CreateFile("second.txt", "second"))),
            tmp_path,
        )
        monkeypatch.setattr(plans, "_write_file", lambda operation: (_ for _ in ()).throw(OSError("failed")))

        with pytest.raises(OSError, match="failed"):
            apply_plan(prepared)

        assert os.stat(target).st_mode & 0o777 == 0o700

    def test_preserves_the_original_error_when_rollback_fails(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        prepared = prepare_plan(
            ChangePlan((CreateDirectory("pkg"), CreateFile("second.txt", "second"))),
            tmp_path,
        )

        def fail_after_concurrent_write(operation: plans.PreparedOperation) -> pathlib.Path | None:
            (tmp_path / "pkg/concurrent.txt").write_text("content")
            raise OSError("apply failed")

        monkeypatch.setattr(plans, "_write_file", fail_after_concurrent_write)

        with pytest.raises(OSError, match="apply failed") as caught:
            apply_plan(prepared)

        assert caught.value.__notes__ == ["Could not roll back pkg; recovery files were preserved."]

    def test_does_not_follow_a_replaced_root_during_rollback(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        root = tmp_path / "root"
        moved = tmp_path / "moved"
        outside = tmp_path / "outside"
        root.mkdir()
        outside.mkdir()
        prepared = prepare_plan(
            ChangePlan((CreateFile("first.txt", "first"), CreateFile("second.txt", "second"))),
            root,
        )
        write = plans._write_file

        def replace_root_then_fail(operation: plans.PreparedOperation) -> pathlib.Path | None:
            if operation.path.name == "second.txt":
                root.rename(moved)
                root.symlink_to(outside, target_is_directory=True)
                raise OSError("failed")
            return write(operation)

        monkeypatch.setattr(plans, "_write_file", replace_root_then_fail)

        with pytest.raises(OSError, match="failed") as caught:
            apply_plan(prepared)

        assert list(outside.iterdir()) == []
        assert (moved / "first.txt").read_text() == "first"
        assert caught.value.__notes__ == ["Could not roll back because the target root changed."]
