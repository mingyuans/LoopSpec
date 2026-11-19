"""`change archive` drops rework records and Gate products of every Plan from the archive."""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path

import pytest

from loopspec import workflow_archive
from tests.workflow_helpers import (
    CHANGE,
    create_approved,
    create_draft,
    fail_gate,
    invoke,
    pass_node,
    project,
    status,
)

QA_FLOW = [
    {"id": "requirements", "use": "requirements"},
    {
        "id": "qa",
        "use": "qa-testing",
        "requires": ["requirements"],
        "on_fail": {"reset": ["requirements"], "max_retries": 2},
    },
]
ATTEMPTS = "plans/001/.attempts"
QA_PASS = "plans/001/artifacts/qa/test/pass.md"


def archived(home: Path) -> Path:
    return home / f"archive/{date.today():%Y-%m}" / CHANGE


def reworked(tmp_path: Path, *, finish: bool = True) -> Path:
    """A Change whose Plan 001 has one rollback in `.attempts/`, optionally complete."""
    home = project(tmp_path, code=False)
    create_approved(home, QA_FLOW)
    pass_node(home, "requirements/proposal")
    fail_gate(home, "qa/test")
    assert invoke(home, "plan", "rollback", "-c", CHANGE, "-p", "001")[0] == 0
    assert (home / "changes" / CHANGE / ATTEMPTS / "001" / "record.yaml").is_file()
    if finish:
        pass_node(home, "requirements/proposal")
        pass_node(home, "qa/test")
        assert status(home)["status"] == "complete"
    return home


def test_archive_drops_attempts_and_keeps_the_rest(tmp_path: Path) -> None:
    home = reworked(tmp_path)
    code, result = invoke(home, "change", "archive", CHANGE)
    assert code == 0 and result["moved"], result
    assert result["dropped"] == [ATTEMPTS, QA_PASS]
    assert "notDropped" not in result
    target = archived(home)
    assert not (target / ATTEMPTS).exists()
    assert not (target / "plans/001/artifacts/qa").exists()  # emptied report dir pruned
    assert (target / "plans/001/artifacts/requirements/proposal.md").is_file()
    for kept in ("state.md", ".workflow.yaml", "plans/001/plan.yaml", "plans/001/artifacts"):
        assert (target / kept).exists(), kept
    assert not (home / "changes" / CHANGE).exists()


def test_archive_without_rework_drops_only_gate_reports(tmp_path: Path) -> None:
    home = project(tmp_path, code=False)
    create_approved(home, QA_FLOW)
    pass_node(home, "requirements/proposal")
    pass_node(home, "qa/test")
    code, result = invoke(home, "change", "archive", CHANGE)
    assert code == 0 and result["dropped"] == [QA_PASS]


def test_dry_run_reports_without_deleting(tmp_path: Path) -> None:
    home = reworked(tmp_path)
    code, result = invoke(home, "change", "archive", CHANGE, "--dry-run")
    assert code == 0 and result["dryRun"] and result["dropped"] == [ATTEMPTS, QA_PASS]
    assert "moved" not in result
    assert (home / "changes" / CHANGE / ATTEMPTS / "001" / "record.yaml").is_file()


def test_forced_archive_drops_attempts_too(tmp_path: Path) -> None:
    home = reworked(tmp_path, finish=False)
    code, result = invoke(home, "change", "archive", CHANGE, "--force")
    assert code == 0 and result["forced"] and result["dropped"] == [ATTEMPTS]
    assert not (archived(home) / ATTEMPTS).exists()


def test_refused_archive_deletes_nothing(tmp_path: Path) -> None:
    home = reworked(tmp_path, finish=False)
    code, result = invoke(home, "change", "archive", CHANGE)
    assert code == 1 and result["error"] == "archive_unsafe"
    assert (home / "changes" / CHANGE / ATTEMPTS / "001" / "record.yaml").is_file()


def test_archive_conflict_deletes_nothing(tmp_path: Path) -> None:
    home = reworked(tmp_path)
    archived(home).mkdir(parents=True)
    code, result = invoke(home, "change", "archive", CHANGE)
    assert code == 1 and result["error"] == "archive_conflict"
    assert (home / "changes" / CHANGE / ATTEMPTS / "001" / "record.yaml").is_file()


def test_attempts_of_every_plan_are_dropped(tmp_path: Path) -> None:
    home = reworked(tmp_path, finish=False)
    assert invoke(home, "plan", "archive", "-c", CHANGE, "-p", "001", "--note", "replan")[0] == 0
    draft = create_draft(home, QA_FLOW)
    shown = invoke(home, "plan", "show", "-c", CHANGE, "-p", draft["plan"])[1]
    approve = ("plan", "approve", "-c", CHANGE, "-p", draft["plan"])
    assert invoke(home, *approve, "--digest", shown["meta"]["digest"])[0] == 0
    pass_node(home, "requirements/proposal")
    fail_gate(home, "qa/test")
    assert invoke(home, "plan", "rollback", "-c", CHANGE, "-p", "002")[0] == 0
    pass_node(home, "requirements/proposal")
    pass_node(home, "qa/test")
    code, result = invoke(home, "change", "archive", CHANGE)
    assert code == 0, result
    assert result["dropped"] == [
        ATTEMPTS,
        "plans/002/.attempts",
        "plans/002/artifacts/qa/test/pass.md",
    ]
    assert not list(archived(home).rglob(".attempts"))


def test_archive_all_drops_attempts(tmp_path: Path) -> None:
    home = reworked(tmp_path)
    code, result = invoke(home, "change", "archive", "--all")
    assert code == 0, result
    [item] = result["archived"]
    assert item["dropped"] == [ATTEMPTS, QA_PASS]
    assert not (archived(home) / ATTEMPTS).exists()


def test_symlinked_attempts_are_refused_before_anything_moves(tmp_path: Path) -> None:
    (tmp_path / "p").mkdir()
    home = project(tmp_path / "p", code=False)
    create_approved(home, QA_FLOW)
    pass_node(home, "requirements/proposal")
    pass_node(home, "qa/test")
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "keep.txt").write_text("keep\n")
    os.symlink(outside, home / "changes" / CHANGE / ATTEMPTS)
    code, result = invoke(home, "change", "archive", CHANGE, "--force")
    assert code == 1 and result["error"] == "unsafe_path"
    assert (home / "changes" / CHANGE).is_dir() and not archived(home).exists()
    assert (outside / "keep.txt").read_text() == "keep\n"


def test_drop_paths_removes_a_symlink_not_its_target(tmp_path: Path) -> None:
    root = tmp_path / "change"
    (root / "plans" / "001").mkdir(parents=True)
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "keep.txt").write_text("keep\n")
    os.symlink(outside, root / ATTEMPTS)
    fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
    try:
        dropped, failed = workflow_archive.drop_paths(fd, [ATTEMPTS])
    finally:
        os.close(fd)
    assert dropped == [ATTEMPTS] and failed == []
    assert not os.path.lexists(root / ATTEMPTS)
    assert (outside / "keep.txt").read_text() == "keep\n"


@pytest.mark.parametrize("error", [PermissionError("denied"), RecursionError("deep")])
def test_cleanup_failure_is_reported_not_raised(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, error: BaseException
) -> None:
    home = reworked(tmp_path)

    def broken(*args: object, **kwargs: object) -> None:
        raise error

    monkeypatch.setattr(workflow_archive.shutil, "rmtree", broken)
    code, result = invoke(home, "change", "archive", CHANGE)
    assert code == 0 and result["moved"], result
    assert result["dropped"] == [QA_PASS] and result["notDropped"] == [ATTEMPTS]
    assert (archived(home) / ATTEMPTS).is_dir()


def test_drop_follows_the_moved_directory_not_the_path(tmp_path: Path) -> None:
    """A tree swapped in at the archive path after the move keeps its .attempts."""
    moved = tmp_path / "moved"
    (moved / ATTEMPTS).mkdir(parents=True)
    fd = os.open(moved, os.O_RDONLY | os.O_DIRECTORY)
    try:
        moved.rename(tmp_path / "elsewhere")
        decoy = tmp_path / "moved"
        (decoy / ATTEMPTS).mkdir(parents=True)
        dropped, failed = workflow_archive.drop_paths(fd, [ATTEMPTS])
    finally:
        os.close(fd)
    assert dropped == [ATTEMPTS] and failed == []
    assert not (tmp_path / "elsewhere" / ATTEMPTS).exists()
    assert (decoy / ATTEMPTS).is_dir()


def test_nothing_is_dropped_when_another_directory_was_moved(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = reworked(tmp_path)
    source = home / "changes" / CHANGE
    swapped = tmp_path / "original"
    real_rename = os.rename

    def swap_then_rename(src: str, dst: str, **kwargs: object) -> None:
        # Between the identity check and the rename, the Change dir is replaced.
        real_rename(source, swapped)
        (source / ATTEMPTS).mkdir(parents=True)
        real_rename(src, dst, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(workflow_archive.os, "rename", swap_then_rename)
    code, result = invoke(home, "change", "archive", CHANGE)
    assert code == 1 and result["error"] in {"concurrent_path_change", "unsafe_path"}
    assert (swapped / ATTEMPTS / "001" / "record.yaml").is_file()
    assert (archived(home) / ATTEMPTS).is_dir()


def test_code_gates_assurance_and_reports_are_dropped(tmp_path: Path) -> None:
    from tests.workflow_helpers import BUGFIX_FLOW, run_until

    home = project(tmp_path)
    create_approved(home, BUGFIX_FLOW)
    (tmp_path / "backend/code.py").write_text("simulated implementation\n")
    run_until(home, "qa/test")
    fail_gate(home, "qa/test")
    assert invoke(home, "plan", "rollback", "-c", CHANGE, "-p", "001")[0] == 0
    for _ in range(32):
        report = status(home)
        if report["isComplete"]:
            break
        pass_node(home, next(n["id"] for n in report["nodes"] if n["status"] == "ready"))
    plan = home / "changes" / CHANGE / "plans/001"
    assert (plan / ".gates").is_dir() and (plan / ".gate-rounds").is_dir()
    (plan / "artifacts/qa/test/acceptance.sh").write_text("echo ok\n")
    declared = workflow_archive.gate_reports(plan.parent.parent, "001")
    expected_reports = {f"plans/001/{p}" for p in declared if (plan / p).exists()}
    assert len(expected_reports) >= 5  # tests, security, review, qa and assurance PASS
    code, result = invoke(home, "change", "archive", CHANGE)
    assert code == 0, result
    dropped = result["dropped"]
    for name in (".attempts", ".gates", ".gate-rounds"):
        assert f"plans/001/{name}" in dropped
    reports = {p for p in dropped if "/artifacts/" in p}
    assert reports == expected_reports
    target = archived(home) / "plans/001"
    remaining = sorted(str(p.relative_to(target)) for p in target.rglob("*") if p.is_file())
    assert not [p for p in remaining if p.startswith((".gates", ".gate-rounds", ".attempts"))]
    for path in reports:
        assert not (archived(home) / path).exists()
    assert "artifacts/qa/test/acceptance.sh" in remaining  # not a declared Gate output
    assert "artifacts/requirements/proposal.md" in remaining
    assert "plan.yaml" in remaining


def test_unreadable_plan_keeps_reports_but_drops_control_dirs(tmp_path: Path) -> None:
    root = tmp_path / "change"
    for name in (".gates/x", ".gate-rounds/y", "artifacts/qa/test"):
        (root / "plans/001" / name).mkdir(parents=True)
    (root / "plans/001/plan.yaml").write_text("not: [valid\n")
    (root / "plans/001/artifacts/qa/test/pass.md").write_text("PASS\n")
    drops = workflow_archive.archive_drops(root)
    assert drops == ["plans/001/.gates", "plans/001/.gate-rounds"]
