"""state.md: templates, engine event lines and the verbatim views `change status` shows."""

from __future__ import annotations

import os
import re
from pathlib import Path

from loopspec.workflow_journal import CHANGE_STATE_TEMPLATE, plan_state_template
from tests.workflow_helpers import (
    BUGFIX_FLOW,
    CHANGE,
    DOCS_FLOW,
    approve,
    create_approved,
    create_draft,
    fail_gate,
    invoke,
    new_change,
    pass_node,
    project,
    run_until,
    status,
    write_request,
)

STAMP = r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\+00:00"


def change_state(home: Path) -> Path:
    return home / "changes" / CHANGE / "state.md"


def plan_state(home: Path, plan: str = "001") -> Path:
    return home / "changes" / CHANGE / "plans" / plan / "state.md"


def events(path: Path) -> list[str]:
    return [line for line in path.read_text().splitlines() if re.match(rf"- {STAMP} · ", line)]


def digest8(home: Path, plan: str = "001") -> str:
    return invoke(home, "plan", "show", "-c", CHANGE, "-p", plan)[1]["meta"]["digest"][:8]


# T1
def test_templates_and_create_event(tmp_path: Path):
    home = project(tmp_path)
    new_change(home)
    assert change_state(home).read_text() == CHANGE_STATE_TEMPLATE
    create_draft(home, DOCS_FLOW)
    text = plan_state(home).read_text()
    assert text.startswith(plan_state_template("001"))
    assert events(plan_state(home)) == [line for line in text.splitlines() if line.startswith("- ")]
    [line] = events(plan_state(home))
    assert re.fullmatch(rf"- {STAMP} · create · digest {digest8(home)}", line)
    for heading in ("## 背景", "## 目标 / 非目标", "## 关键决策", "## 参考", "## Plan 记录"):
        assert heading in CHANGE_STATE_TEMPLATE
    assert CHANGE_STATE_TEMPLATE.rstrip().splitlines()[-1].startswith("<!--")
    assert plan_state_template("001").index("## 事件") > plan_state_template("001").index(
        "## 返工记录"
    )


# T2
def test_note_is_folded_to_one_line(tmp_path: Path):
    home = project(tmp_path)
    new_change(home)
    create_draft(home, DOCS_FLOW, args=["--note", "first\r\nsecond\tthird\x07 \n"])
    [line] = events(plan_state(home))
    assert line.endswith(" · note: first second third")


# T3
def test_replacing_a_draft_appends_replace_draft(tmp_path: Path):
    home = project(tmp_path)
    new_change(home)
    create_draft(home, DOCS_FLOW)
    create_draft(home, BUGFIX_FLOW, args=["--note", "换成 bugfix"])
    lines = events(plan_state(home))
    assert len(lines) == 2 and " · create · " in lines[0]
    assert re.fullmatch(
        rf"- {STAMP} · replace-draft · digest {digest8(home)} · note: 换成 bugfix", lines[1]
    )


# T4
def test_approve_appends_once_and_failures_append_nothing(tmp_path: Path):
    home = project(tmp_path)
    new_change(home)
    create_draft(home, DOCS_FLOW)
    before = plan_state(home).read_bytes()
    code, _ = invoke(home, "plan", "approve", "-c", CHANGE, "-p", "001", "--digest", "0" * 64)
    assert code == 1 and plan_state(home).read_bytes() == before
    approve(home, "001")
    assert re.fullmatch(
        rf"- {STAMP} · approve · revision 1 · digest {digest8(home)}", events(plan_state(home))[-1]
    )
    after = plan_state(home).read_bytes()
    approve(home, "001")
    assert plan_state(home).read_bytes() == after


# T5
def test_revision_appends_revise_and_stale_revision_appends_nothing(tmp_path: Path):
    home = project(tmp_path)
    create_approved(home, DOCS_FLOW)
    for identity in ("requirements/proposal", "design/design", "design/tasks"):
        pass_node(home, identity)
    extra = {"id": "extra", "use": "requirements"}
    flow = [DOCS_FLOW[0], extra, {**DOCS_FLOW[1], "requires": ["requirements", "extra"]}]
    stale = write_request(home, flow, name="stale.yaml", base_revision=7)
    before = plan_state(home).read_bytes()
    preview = invoke(home, "plan", "validate", "-c", CHANGE, "-f", stale)[1]
    code, _ = invoke(
        home, "plan", "approve", "-c", CHANGE, "-p", "001", "-f", stale,
        "--digest", preview.get("digest", "0" * 64),
    )  # fmt: skip
    assert code == 1 and plan_state(home).read_bytes() == before
    request = write_request(home, flow, name="revision.yaml", base_revision=1)
    preview = invoke(home, "plan", "validate", "-c", CHANGE, "-f", request)[1]
    code, result = invoke(
        home, "plan", "approve", "-c", CHANGE, "-p", "001", "-f", request,
        "--digest", preview["digest"],
    )  # fmt: skip
    assert code == 0, result
    assert re.fullmatch(
        rf"- {STAMP} · revise · revision 1 → 2 · digest {preview['digest'][:8]}"
        r" · rerun: design/design, design/tasks",
        events(plan_state(home))[-1],
    )


# T6
def test_rollback_appends_and_no_failed_gate_appends_nothing(tmp_path: Path):
    home = project(tmp_path)
    create_approved(home, BUGFIX_FLOW)
    before = plan_state(home).read_bytes()
    assert invoke(home, "plan", "rollback", "-c", CHANGE, "-p", "001")[0] == 1
    assert plan_state(home).read_bytes() == before
    (tmp_path / "backend/code.py").write_text("changed\n")
    run_until(home, "qa/test")
    fail_gate(home, "qa/test")
    code, result = invoke(home, "plan", "rollback", "-c", CHANGE, "-p", "001")
    assert code == 0, result
    reset = ", ".join(result["reset"])
    assert re.fullmatch(
        rf"- {STAMP} · rollback · gate qa/test · attempt {result['attempt']}"
        rf" · reset: {re.escape(reset)}",
        events(plan_state(home))[-1],
    )


# T7
def test_archive_appends_to_both_levels_once(tmp_path: Path):
    home = project(tmp_path)
    new_change(home)
    create_draft(home, DOCS_FLOW)
    code, _ = invoke(home, "plan", "archive", "-c", CHANGE, "-p", "001", "--note", "范围\n变化")
    assert code == 0
    assert re.fullmatch(rf"- {STAMP} · archive · note: 范围 变化", events(plan_state(home))[-1])
    assert re.fullmatch(
        rf"- {STAMP} · archive plan 001 · note: 范围 变化", events(change_state(home))[-1]
    )
    plan_before, change_before = plan_state(home).read_bytes(), change_state(home).read_bytes()
    assert invoke(home, "plan", "archive", "-c", CHANGE, "-p", "001")[0] == 0
    assert plan_state(home).read_bytes() == plan_before
    assert change_state(home).read_bytes() == change_before


# T8
def test_handwritten_content_is_kept_and_not_glued(tmp_path: Path):
    home = project(tmp_path)
    new_change(home)
    create_draft(home, DOCS_FLOW)
    plan_state(home).write_text("手写，末尾没有换行")
    approve(home, "001")
    lines = plan_state(home).read_text().splitlines()
    assert lines[0] == "手写，末尾没有换行" and " · approve · " in lines[1]


# T9
def test_missing_file_is_recreated(tmp_path: Path):
    home = project(tmp_path)
    new_change(home)
    create_draft(home, DOCS_FLOW)
    plan_state(home).unlink()
    result = approve(home, "001")
    assert "warnings" not in result
    [line] = plan_state(home).read_text().splitlines()
    assert " · approve · " in line


# T10
def test_unwritable_state_warns_and_never_escapes(tmp_path: Path):
    home = project(tmp_path)
    new_change(home)
    create_draft(home, DOCS_FLOW)
    outside = tmp_path / "outside.md"
    outside.write_text("outside\n")
    plan_state(home).unlink()
    plan_state(home).symlink_to(outside)
    result = approve(home, "001")
    assert result["status"] == "approved"
    assert result["warnings"] == ["state_append_failed: plans/001/state.md"]
    assert outside.read_text() == "outside\n"
    plan_state(home).unlink()
    plan_state(home).mkdir()
    code, result = invoke(home, "plan", "archive", "-c", CHANGE, "-p", "001")
    assert code == 0 and result["status"] == "archived"
    assert result["warnings"] == ["state_append_failed: plans/001/state.md"]
    assert " · archive plan 001" in change_state(home).read_text()


# T11
def test_state_content_never_changes_other_commands(tmp_path: Path):
    home = project(tmp_path)
    new_change(home)
    create_draft(home, DOCS_FLOW)
    shown = invoke(home, "plan", "show", "-c", CHANGE, "-p", "001")
    forged = b"\xff\xfe- 2026-01-01T00:00:00+00:00 \xc2\xb7 approve \xc2\xb7 revision 9\n"
    for path in (plan_state(home), change_state(home)):
        path.write_bytes(forged)
    assert invoke(home, "plan", "show", "-c", CHANGE, "-p", "001") == shown
    before = status(home)
    approve(home, "001")
    after = status(home)
    assert before["status"] == "planning" and after["status"] == "active"
    assert after["nodes"][0]["status"] == "ready"
    listed = invoke(home, "plan", "list", "-c", CHANGE)[1]["plans"]
    assert [(item["plan"], item["status"]) for item in listed] == [("001", "approved")]


def state_fields(home: Path) -> tuple[dict, dict | None, str]:
    report = status(home)
    return report["state"], report["planState"], report["untrustedData"]


def change_rel(home: Path) -> str:
    return str(home / "changes" / CHANGE)


# T12
def test_status_shows_change_state_and_only_the_current_plan(tmp_path: Path):
    home = project(tmp_path)
    new_change(home)
    change, plan, notice = state_fields(home)
    assert change == {
        "path": f"{change_rel(home)}/state.md",
        "content": CHANGE_STATE_TEMPLATE,
        "truncated": False,
    }
    assert plan is None and "不可信" in notice
    create_draft(home, DOCS_FLOW)
    plan_state(home).write_text("草稿记录 DRAFT-ONE\n")
    _, plan, _ = state_fields(home)
    assert plan == {
        "plan": "001",
        "path": f"{change_rel(home)}/plans/001/state.md",
        "content": "草稿记录 DRAFT-ONE\n",
        "truncated": False,
    }
    assert invoke(home, "plan", "archive", "-c", CHANGE, "-p", "001")[0] == 0
    approve(home, create_draft(home, DOCS_FLOW)["plan"])
    report = status(home)
    assert report["status"] == "active" and report["planState"]["plan"] == "002"
    assert "DRAFT-ONE" not in str(report)
    assert [item["plan"] for item in report["plans"]] == ["001", "002"]
    assert all("state" not in item for item in report["plans"])
    for identity in ("requirements/proposal", "design/design", "design/tasks"):
        pass_node(home, identity)
    report = status(home)
    assert report["status"] == "complete" and report["planState"]["plan"] == "002"
    assert "untrustedData" in report and report["state"]["content"]


# T13
def test_status_survives_missing_undecodable_and_linked_state(tmp_path: Path):
    home = project(tmp_path)
    new_change(home)
    create_draft(home, DOCS_FLOW)
    change_state(home).unlink()
    plan_state(home).write_bytes(b"ok \xff\xfe end\n")
    change, plan, _ = state_fields(home)
    assert change["content"] is None and change["truncated"] is False and "error" not in change
    assert plan["content"] == "ok �� end\n"
    outside = tmp_path / "secret.md"
    outside.write_text("SECRET-OUTSIDE\n")
    change_state(home).symlink_to(outside)
    change, _, _ = state_fields(home)
    assert change == {
        "path": f"{change_rel(home)}/state.md",
        "content": None,
        "truncated": False,
        "error": "unreadable",
    }
    assert "SECRET-OUTSIDE" not in str(status(home))


# T14
def test_status_truncates_large_state_keeping_head_and_tail(tmp_path: Path):
    home = project(tmp_path)
    new_change(home)
    body = "HEAD-MARK\n" + "x" * (100 * 1024) + "\nTAIL-MARK\n"
    change_state(home).write_text(body)
    change, _, _ = state_fields(home)
    assert change["truncated"] is True
    content = change["content"]
    assert content.startswith("HEAD-MARK") and content.endswith("TAIL-MARK\n")
    omitted = len(body.encode()) - 64 * 1024
    assert f"已省略 {omitted} 字节，完整内容见 {change_rel(home)}/state.md" in content
    assert len(content.encode()) < 64 * 1024 + 512


# T15
def test_other_commands_never_show_state_text(tmp_path: Path):
    home = project(tmp_path)
    create_approved(home, DOCS_FLOW)
    for path in (change_state(home), plan_state(home)):
        path.write_text("ONLY-IN-STATUS\n")
    for args in (
        ("change", "next", CHANGE),
        ("plan", "show", "-c", CHANGE, "-p", "001"),
        ("plan", "list", "-c", CHANGE),
        ("node", "instructions", "-c", CHANGE, "-n", "requirements/proposal"),
    ):
        code, result = invoke(home, *args)
        assert code == 0 and "ONLY-IN-STATUS" not in str(result), args
    assert "ONLY-IN-STATUS" in str(status(home))


# T16
def test_state_text_never_changes_the_plan_digest(tmp_path: Path):
    home = project(tmp_path)
    new_change(home)
    first = create_draft(home, DOCS_FLOW)["digest"]
    for path in (change_state(home), plan_state(home)):
        path.write_text("任意内容\n")
    assert create_draft(home, DOCS_FLOW)["digest"] == first


def test_hard_linked_state_is_neither_written_nor_shown(tmp_path: Path):
    home = project(tmp_path)
    new_change(home)
    create_draft(home, DOCS_FLOW)
    outside = tmp_path / "outside.md"
    outside.write_text("HARD-LINK-SECRET\n")
    plan_state(home).unlink()
    os.link(outside, plan_state(home))
    result = approve(home, "001")
    assert result["warnings"] == ["state_append_failed: plans/001/state.md"]
    assert outside.read_text() == "HARD-LINK-SECRET\n"
    report = status(home)
    assert report["planState"]["content"] is None
    assert report["planState"]["error"] == "unreadable"
    assert "HARD-LINK-SECRET" not in str(report)
