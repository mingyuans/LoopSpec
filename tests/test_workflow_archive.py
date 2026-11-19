"""`change archive`: two steps with the memory review, and what the archive drops."""

from __future__ import annotations

import json
import os
import re
from datetime import date
from pathlib import Path

import pytest

from loopspec import workflow_archive
from tests.workflow_helpers import (
    CHANGE,
    archive_change,
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
    code, result = archive_change(home)
    assert code == 0, result
    [item] = result["archived"]
    assert item["moved"] and item["dropped"] == [ATTEMPTS, QA_PASS]
    assert "notDropped" not in item
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
    code, result = archive_change(home)
    assert code == 0 and result["archived"][0]["dropped"] == [QA_PASS]


def test_first_step_archives_nothing_and_issues_a_review(tmp_path: Path) -> None:
    home = reworked(tmp_path)
    before = sorted(str(p) for p in (home / "changes" / CHANGE).rglob("*"))
    code, result = invoke(home, "change", "archive", CHANGE)
    assert code == 0, result
    [change] = result["changes"]
    assert change["dropped"] == [ATTEMPTS, QA_PASS] and "moved" not in change
    assert sorted(str(p) for p in (home / "changes" / CHANGE).rglob("*")) == before
    assert re.fullmatch(r"[0-9a-f]{64}", result["archiveId"])
    review = result["memoryReview"]
    assert "Memory maintenance procedure" in review["instructions"]
    assert review["memoryIndex"]["topics"] == []
    inputs = change["inputs"]
    assert str(home.absolute() / "changes" / CHANGE / "state.md") in inputs["stateFiles"]
    assert any(p.endswith("requirements/proposal.md") for p in inputs["artifacts"])
    assert any(p.endswith(ATTEMPTS) for p in inputs["willBeDeleted"])
    confirm_step = f"loopspec change archive --confirm {result['archiveId']}"
    assert result["nextSteps"][0].startswith(confirm_step)
    ticket = home / ".cache/archive" / f"{result['archiveId']}.json"
    assert ticket.is_file() and (home / ".cache/archive/.gitignore").read_text() == "*\n"


def test_forced_archive_drops_attempts_too(tmp_path: Path) -> None:
    home = reworked(tmp_path, finish=False)
    code, result = archive_change(home, CHANGE, "--force")
    assert code == 0 and result["archived"][0]["forced"]
    assert result["archived"][0]["dropped"] == [ATTEMPTS]
    assert not (archived(home) / ATTEMPTS).exists()


def test_refused_archive_deletes_nothing(tmp_path: Path) -> None:
    home = reworked(tmp_path, finish=False)
    code, result = invoke(home, "change", "archive", CHANGE)
    assert code == 1 and result["error"] == "archive_unsafe"
    assert (home / "changes" / CHANGE / ATTEMPTS / "001" / "record.yaml").is_file()


def test_archive_conflict_deletes_nothing(tmp_path: Path) -> None:
    home = reworked(tmp_path)
    archived(home).mkdir(parents=True)
    code, result = archive_change(home)
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
    code, result = archive_change(home)
    assert code == 0, result
    assert result["archived"][0]["dropped"] == [
        ATTEMPTS,
        "plans/002/.attempts",
        "plans/002/artifacts/qa/test/pass.md",
    ]
    assert not list(archived(home).rglob(".attempts"))


def test_archive_all_drops_attempts(tmp_path: Path) -> None:
    home = reworked(tmp_path)
    code, result = archive_change(home, "--all")
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
    code, result = archive_change(home)
    assert code == 0, result
    [item] = result["archived"]
    assert item["dropped"] == [QA_PASS] and item["notDropped"] == [ATTEMPTS]
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

    code, first = invoke(home, "change", "archive", CHANGE)
    assert code == 0, first
    monkeypatch.setattr(workflow_archive.os, "rename", swap_then_rename)
    code, result = invoke(
        home, "change", "archive", "--confirm", first["archiveId"], "--memory", "none",
        "--note", "nothing reusable",
    )
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
    code, result = archive_change(home)
    assert code == 0, result
    dropped = result["archived"][0]["dropped"]
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


# ------------------------------------------------------------- the review step


def prepared(home: Path, *args: str) -> str:
    code, result = invoke(home, "change", "archive", *(args or (CHANGE,)))
    assert code == 0 and result["archiveId"], result
    return result["archiveId"]


def confirm(home: Path, archive_id: str, *extra: str) -> tuple[int, dict]:
    return invoke(home, "change", "archive", "--confirm", archive_id, *extra)


def write_topic(home: Path, topic: str, text: str = "# Lesson\n\n- reusable\n") -> None:
    (home / "memory").mkdir(exist_ok=True)
    (home / "memory" / f"{topic}.md").write_text(text)


@pytest.mark.parametrize(
    "extra",
    [[], ["--memory", "none"], ["--note", "x"], ["--memory", "maybe", "--note", "x"]],
)
def test_confirm_requires_both_review_fields(tmp_path: Path, extra: list[str]) -> None:
    home = reworked(tmp_path)
    archive_id = prepared(home)
    code, result = confirm(home, archive_id, *extra)
    assert code == 1 and result["error"] in {"memory_review_required", "workflow_invalid"}
    assert (home / "changes" / CHANGE).is_dir()


@pytest.mark.parametrize("note", ["   ", "x" * 1001, "see <!-- hidden -->"])
def test_confirm_rejects_bad_notes(tmp_path: Path, note: str) -> None:
    home = reworked(tmp_path)
    code, result = confirm(home, prepared(home), "--memory", "none", "--note", note)
    assert code == 1 and result["error"] == "workflow_invalid"
    assert (home / "changes" / CHANGE).is_dir()


def test_unknown_or_malformed_ticket_is_refused(tmp_path: Path) -> None:
    home = reworked(tmp_path)
    archive_id = prepared(home)
    for value in ("f" * 64, "../../x", "ABC"):
        code, result = confirm(home, value, "--memory", "none", "--note", "n")
        assert code == 1 and result["error"] == "archive_ticket_not_found", value
    path = home / ".cache/archive" / f"{archive_id}.json"
    ticket = json.loads(path.read_text())
    ticket["entries"][0]["forced"] = True
    path.write_text(json.dumps(ticket))
    code, result = confirm(home, archive_id, "--memory", "none", "--note", "n")
    assert code == 1 and result["error"] == "archive_ticket_invalid"


def test_change_edited_after_the_first_step_is_stale(tmp_path: Path) -> None:
    home = reworked(tmp_path)
    archive_id = prepared(home)
    proposal = home / "changes" / CHANGE / "plans/001/artifacts/requirements/proposal.md"
    proposal.write_text("edited after review\n")
    code, result = confirm(home, archive_id, "--memory", "none", "--note", "n")
    assert code == 1 and result["error"] == "archive_ticket_stale"
    assert (home / "changes" / CHANGE).is_dir()


def test_updated_without_any_memory_change_is_refused(tmp_path: Path) -> None:
    home = reworked(tmp_path)
    archive_id = prepared(home)
    (home / "memory").mkdir(exist_ok=True)
    (home / "memory" / "notes.txt").write_text("not a topic\n")  # ignored by memory rules
    code, result = confirm(home, archive_id, "--memory", "updated", "--note", "added lessons")
    assert code == 1 and result["error"] == "memory_review_missing"
    assert (home / "changes" / CHANGE).is_dir()


def test_none_while_memory_changed_is_refused(tmp_path: Path) -> None:
    home = reworked(tmp_path)
    archive_id = prepared(home)
    write_topic(home, "archive-rules")
    code, result = confirm(home, archive_id, "--memory", "none", "--note", "nothing")
    assert code == 1 and result["error"] == "memory_review_mismatch"
    assert "archive-rules" in result["message"]


def test_updated_review_is_recorded_and_the_ticket_consumed(tmp_path: Path) -> None:
    home = reworked(tmp_path)
    write_topic(home, "existing")
    archive_id = prepared(home)
    write_topic(home, "existing", "# Lesson\n\n- revised\n")
    write_topic(home, "archive-rules")
    code, result = confirm(
        home, archive_id, "--memory", "updated", "--note", "records the archive rules"
    )
    assert code == 0, result
    assert result["memoryReview"] == {
        "memory": "updated",
        "note": "records the archive rules",
        "changedTopics": ["archive-rules", "existing"],
    }
    state = (archived(home) / "state.md").read_text()
    assert "归档前 memory 审阅" in state and "结论：updated" in state
    assert "archive-rules, existing" in state and "records the archive rules" in state
    assert not (home / ".cache/archive" / f"{archive_id}.json").exists()
    code, again = confirm(home, archive_id, "--memory", "updated", "--note", "again")
    assert code == 1 and again["error"] == "archive_ticket_not_found"


def test_none_review_is_recorded(tmp_path: Path) -> None:
    home = reworked(tmp_path)
    code, result = confirm(home, prepared(home), "--memory", "none", "--note", "only a demo")
    assert code == 0, result
    state = (archived(home) / "state.md").read_text()
    assert "结论：none" in state and "变化的 topic：无" in state and "only a demo" in state


def test_all_confirms_every_change_with_one_review(tmp_path: Path) -> None:
    home = reworked(tmp_path)
    for name in ("SECOND1",):
        create_approved(home, QA_FLOW, name)
        pass_node(home, "requirements/proposal", name)
        pass_node(home, "qa/test", name)
    archive_id = prepared(home, "--all")
    write_topic(home, "batch-lessons")
    code, result = confirm(home, archive_id, "--memory", "updated", "--note", "batch")
    assert code == 0, result
    assert [item["changeName"] for item in result["archived"]] == [CHANGE, "SECOND1"]
    for name in (CHANGE, "SECOND1"):
        state = (home / f"archive/{date.today():%Y-%m}" / name / "state.md").read_text()
        assert "batch-lessons" in state


def test_failed_batch_resumes_with_the_same_ticket(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = reworked(tmp_path)
    create_approved(home, QA_FLOW, "SECOND1")
    pass_node(home, "requirements/proposal", "SECOND1")
    pass_node(home, "qa/test", "SECOND1")
    archive_id = prepared(home, "--all")
    real_move = workflow_archive.move
    calls = []

    def fail_second(*args, **kwargs):  # type: ignore[no-untyped-def]
        calls.append(args[3])
        if args[3] == "SECOND1" and len(calls) == 2:
            raise OSError("disk full")
        return real_move(*args, **kwargs)

    monkeypatch.setattr(workflow_archive, "move", fail_second)
    code, _ = confirm(home, archive_id, "--memory", "none", "--note", "n")
    assert code != 0
    assert archived(home).is_dir() and (home / "changes" / "SECOND1").is_dir()
    code, result = confirm(home, archive_id, "--memory", "none", "--note", "n")
    assert code == 0, result
    assert [item["changeName"] for item in result["archived"]] == ["SECOND1"]
    state = (home / f"archive/{date.today():%Y-%m}" / "SECOND1" / "state.md").read_text()
    assert state.count("归档前 memory 审阅") == 1


def test_dry_run_option_is_gone(tmp_path: Path) -> None:
    home = reworked(tmp_path)
    code, _ = invoke(home, "change", "archive", CHANGE, "--dry-run")
    assert code == 2
