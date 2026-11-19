"""`change archive` drops the rework records (`.attempts/`) of every Plan from the archive."""

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
    assert result["droppedAttempts"] == [ATTEMPTS]
    assert "attemptsNotDropped" not in result
    target = archived(home)
    assert not (target / ATTEMPTS).exists()
    for kept in ("state.md", ".workflow.yaml", "plans/001/plan.yaml", "plans/001/artifacts"):
        assert (target / kept).exists(), kept
    assert not (home / "changes" / CHANGE).exists()


def test_archive_without_rework_drops_nothing(tmp_path: Path) -> None:
    home = project(tmp_path, code=False)
    create_approved(home, QA_FLOW)
    pass_node(home, "requirements/proposal")
    pass_node(home, "qa/test")
    code, result = invoke(home, "change", "archive", CHANGE)
    assert code == 0 and result["droppedAttempts"] == []


def test_dry_run_reports_without_deleting(tmp_path: Path) -> None:
    home = reworked(tmp_path)
    code, result = invoke(home, "change", "archive", CHANGE, "--dry-run")
    assert code == 0 and result["dryRun"] and result["droppedAttempts"] == [ATTEMPTS]
    assert "moved" not in result
    assert (home / "changes" / CHANGE / ATTEMPTS / "001" / "record.yaml").is_file()


def test_forced_archive_drops_attempts_too(tmp_path: Path) -> None:
    home = reworked(tmp_path, finish=False)
    code, result = invoke(home, "change", "archive", CHANGE, "--force")
    assert code == 0 and result["forced"] and result["droppedAttempts"] == [ATTEMPTS]
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
    assert sorted(result["droppedAttempts"]) == [ATTEMPTS, "plans/002/.attempts"]
    assert not list(archived(home).rglob(".attempts"))


def test_archive_all_drops_attempts(tmp_path: Path) -> None:
    home = reworked(tmp_path)
    code, result = invoke(home, "change", "archive", "--all")
    assert code == 0, result
    [item] = result["archived"]
    assert item["droppedAttempts"] == [ATTEMPTS]
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


def test_drop_attempts_removes_a_symlink_not_its_target(tmp_path: Path) -> None:
    root = tmp_path / "change"
    (root / "plans" / "001").mkdir(parents=True)
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "keep.txt").write_text("keep\n")
    os.symlink(outside, root / ATTEMPTS)
    dropped, failed = workflow_archive.drop_attempts(root, [ATTEMPTS])
    assert dropped == [ATTEMPTS] and failed == []
    assert not os.path.lexists(root / ATTEMPTS)
    assert (outside / "keep.txt").read_text() == "keep\n"


def test_cleanup_failure_is_reported_not_raised(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = reworked(tmp_path)

    def broken(*args: object, **kwargs: object) -> None:
        raise PermissionError("denied")

    monkeypatch.setattr(workflow_archive.shutil, "rmtree", broken)
    code, result = invoke(home, "change", "archive", CHANGE)
    assert code == 0 and result["moved"], result
    assert result["droppedAttempts"] == [] and result["attemptsNotDropped"] == [ATTEMPTS]
    assert (archived(home) / ATTEMPTS).is_dir()
