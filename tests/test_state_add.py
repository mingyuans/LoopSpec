"""`loopspec state add`, the section registry, safe byte-level insertion and stateProtocol."""

from __future__ import annotations

import fcntl
import hashlib
import os
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

from loopspec import workflow_state_notes as notes
from loopspec.cli import app
from loopspec.errors import WorkflowError
from loopspec.workflow_io import (
    MAX_FILE_BYTES,
    ensure_file_identity,
    read_regular_file,
    write_lock,
)
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
    project,
    run_until,
    runner,
)

DATE = r"\d{4}-\d{2}-\d{2}"


def change_state(home: Path) -> Path:
    return home / "changes" / CHANGE / "state.md"


def plan_state(home: Path, plan: str = "001") -> Path:
    return home / "changes" / CHANGE / "plans" / plan / "state.md"


def add(home: Path, *args: str) -> tuple[int, dict]:
    return invoke(home, "state", "add", "-c", CHANGE, *args)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def section_lines(path: Path, title: str) -> list[str]:
    """Non-blank, non-comment lines of the `## title` section."""
    lines = path.read_text().splitlines()
    start = lines.index(f"## {title}")
    out = []
    for line in lines[start + 1 :]:
        if line.startswith("## "):
            break
        if line.strip() and not line.startswith("<!--") and not line.endswith("-->"):
            out.append(line)
    return out


def draft_home(tmp_path: Path) -> Path:
    home = project(tmp_path)
    new_change(home)
    create_draft(home, DOCS_FLOW)
    return home


# T1 -----------------------------------------------------------------------------------


def test_registry_declares_every_section_with_its_rules():
    assert set(notes.CHANGE_ORDER) == {
        "background", "goals", "decision", "open-question", "reference", "plan-record",
    }  # fmt: skip
    assert set(notes.PLAN_ORDER) == {"assumption", "deviation", "open-question", "rework", "events"}
    for key in {*notes.CHANGE_ORDER, *notes.PLAN_ORDER}:
        section = notes.SECTIONS[key]
        assert section.title and section.writer in (notes.AGENT, notes.ENGINE)
        for spec in section.scopes.values():
            assert spec.boundary and spec.when and spec.format and spec.hint
    assert notes.SECTIONS["plan-record"].writer == notes.ENGINE
    assert notes.SECTIONS["events"].writer == notes.ENGINE
    assert set(notes.SECTIONS["open-question"].scopes) == {"change", "plan"}
    assert "human-decision" not in notes.SECTIONS


@pytest.mark.parametrize(
    ("kwargs", "expected"),
    [
        ({"section": "background"}, rf"- {DATE} 内容"),
        (
            {"section": "decision", "actor": "HUMAN", "by": "用户"},
            rf"- {DATE} \[HUMAN: 用户\] 内容",
        ),
        (
            {"section": "decision", "actor": "MODEL", "by": "BE"},
            rf"- {DATE} \[MODEL: BE\] 内容",
        ),
        ({"section": "open-question", "scope": "change"}, rf"- {DATE} 内容"),
        (
            {"section": "open-question", "scope": "plan", "node": "design/design"},
            rf"- {DATE} \[design/design\] 内容",
        ),
        ({"section": "assumption", "node": "design/design"}, rf"- {DATE} \[design/design\] 内容"),
    ],
)
def test_every_agent_entry_is_a_dated_single_line_bullet(kwargs: dict, expected: str):
    request = notes.validate_request(
        text="内容", scope=kwargs.get("scope"), plan=None, node=kwargs.get("node"),
        actor=kwargs.get("actor"), by=kwargs.get("by"), section=kwargs["section"],
    )  # fmt: skip
    line = notes.render_entry(request, "2026-11-08", attempt=None, seq=None)
    assert re.fullmatch(expected.replace(DATE, "2026-11-08"), line) and "\n" not in line


def test_rework_entry_shows_round_and_rollback_seq():
    request = notes.validate_request(
        section="rework", text="认识", scope=None, plan=None, node="qa/test", actor=None, by=None
    )
    line = notes.render_entry(request, "2026-11-08", attempt=2, seq=4)
    assert line == "- 2026-11-08 [qa/test] attempt 2（rollback #4）：认识"


# T2 -----------------------------------------------------------------------------------


def headings(text: str) -> list[str]:
    return [line for line in text.splitlines() if line.startswith("## ")]


def test_templates_follow_the_registry_and_end_with_the_engine_section(tmp_path: Path):
    assert headings(notes.change_template()) == [
        "## 背景", "## 目标与边界", "## 决策", "## 待解决问题", "## 参考", "## Plan 记录",
    ]  # fmt: skip
    assert headings(notes.plan_template("001")) == [
        "## 假设", "## 偏离", "## 待解决问题", "## 返工记录", "## 事件",
    ]  # fmt: skip
    old = ("人工决策", "假设与偏离", "关键决策", "目标 / 非目标")
    for text in (notes.change_template(), notes.plan_template("001")):
        assert not any(name in text for name in old)
        assert text.rstrip().splitlines()[-1].startswith("<!--")
    home = project(tmp_path)
    new_change(home)
    assert change_state(home).read_text() == notes.change_template()
    create_draft(home, DOCS_FLOW)
    assert plan_state(home).read_text().startswith(notes.plan_template("001"))


# T3 -----------------------------------------------------------------------------------


def test_change_level_sections_receive_their_entries(tmp_path: Path):
    home = draft_home(tmp_path)
    for section, title in (("background", "背景"), ("goals", "目标与边界"), ("reference", "参考")):
        code, result = add(home, "--section", section, "--text", f"{section} 记录")
        assert code == 0, result
        assert result["scope"] == "change" and result["plan"] is None
        assert section_lines(change_state(home), title) == [f"{result['line']}"]
    code, result = add(
        home, "--section", "decision", "--actor", "HUMAN", "--by", "用户", "--text", "采用方案 A"
    )
    assert code == 0, result
    [line] = section_lines(change_state(home), "决策")
    assert re.fullmatch(rf"- {DATE} \[HUMAN: 用户\] 采用方案 A", line)
    assert section_lines(change_state(home), "待解决问题") == []


# T4 -----------------------------------------------------------------------------------


def test_plan_sections_work_on_draft_and_approved_plans(tmp_path: Path):
    home = draft_home(tmp_path)
    code, result = add(home, "--section", "assumption", "-n", "design/design", "--text", "前提 X")
    assert code == 0, result
    assert result["scope"] == "plan" and result["plan"] == "001"
    assert section_lines(plan_state(home), "假设") == [result["line"]]
    approve(home, "001")
    code, result = add(
        home, "--section", "deviation", "-p", "001", "-n", "design/design", "--text", "有偏离"
    )
    assert code == 0, result
    assert section_lines(plan_state(home), "偏离") == [result["line"]]
    assert section_lines(plan_state(home), "假设") != []
    shown = invoke(home, "plan", "show", "-c", CHANGE, "-p", "001")[1]
    assert shown["meta"]["status"] == "approved" and shown["meta"]["revision"] == 1


def test_a_draft_is_recorded_without_being_approved(tmp_path: Path):
    home = draft_home(tmp_path)
    assert add(home, "--section", "assumption", "-n", "design/design", "--text", "t")[0] == 0
    shown = invoke(home, "plan", "show", "-c", CHANGE, "-p", "001")[1]
    assert shown["meta"]["status"] == "draft"


def test_plan_scope_needs_an_existing_unarchived_plan(tmp_path: Path):
    home = project(tmp_path)
    new_change(home)
    code, result = add(home, "--section", "assumption", "-n", "x", "--text", "t")
    assert code == 1 and result["error"] == "plan_not_found"
    create_draft(home, DOCS_FLOW)
    code, result = add(home, "--section", "assumption", "-p", "009", "-n", "x", "--text", "t")
    assert code == 1 and result["error"] == "plan_not_found"
    assert invoke(home, "plan", "archive", "-c", CHANGE, "-p", "001")[0] == 0
    before = digest(plan_state(home))
    code, result = add(
        home, "--section", "assumption", "-p", "001", "-n", "design/design", "--text", "t"
    )
    assert code == 1 and result["error"] == "plan_archived"
    assert digest(plan_state(home)) == before
    code, result = add(home, "--section", "assumption", "-n", "design/design", "--text", "t")
    assert code == 1 and result["error"] == "plan_not_found"


# T5 -----------------------------------------------------------------------------------


def test_entries_append_in_order_and_keep_comments_and_blank_lines(tmp_path: Path):
    home = draft_home(tmp_path)
    before = change_state(home).read_text()
    for index in range(3):
        assert add(home, "--section", "background", "--text", f"第{index}条")[0] == 0
    lines = section_lines(change_state(home), "背景")
    assert [line.split(" ", 2)[2] for line in lines] == ["第0条", "第1条", "第2条"]
    after = change_state(home).read_text()
    assert after.count("<!--") == before.count("<!--") and "\n\n## 目标与边界" in after
    original = lines[0]
    assert add(home, "--section", "background", "--text", "更正：第0条作废")[0] == 0
    assert section_lines(change_state(home), "背景")[0] == original


# T6 -----------------------------------------------------------------------------------


SAMPLE = "## A\n\n<!-- a -->\n\n## B\n\n<!-- b -->\n"


def test_insert_keeps_every_other_byte_for_lf_crlf_and_missing_final_newline():
    entry = "- X"
    out = notes.insert_entry(SAMPLE.encode(), "A", entry)
    assert out == b"## A\n\n<!-- a -->\n- X\n\n## B\n\n<!-- b -->\n"
    crlf = SAMPLE.replace("\n", "\r\n").encode()
    out = notes.insert_entry(crlf, "A", entry)
    assert out == b"## A\r\n\r\n<!-- a -->\r\n- X\r\n\r\n## B\r\n\r\n<!-- b -->\r\n"
    mixed = b"## A\r\n\r\n<!-- a -->\r\n\n## B\n<!-- b -->\n"
    assert notes.insert_entry(mixed, "A", entry) == (
        b"## A\r\n\r\n<!-- a -->\r\n- X\r\n\n## B\n<!-- b -->\n"
    )
    bare = b"## A\n\n<!-- a -->\n\n## B\n\n<!-- b -->"
    out = notes.insert_entry(bare, "B", entry)
    assert out == bare + b"\n- X" and out.startswith(bare)
    assert notes.insert_entry(bare, "A", entry) == (
        b"## A\n\n<!-- a -->\n- X\n\n## B\n\n<!-- b -->"
    )


def test_engine_tail_and_event_lines_are_untouched(tmp_path: Path):
    home = draft_home(tmp_path)
    approve(home, "001")
    before = plan_state(home).read_bytes()
    marker = before.index("## 事件".encode())
    assert add(home, "--section", "assumption", "-n", "design/design", "--text", "t")[0] == 0
    after = plan_state(home).read_bytes()
    assert after[after.index("## 事件".encode()) :] == before[marker:]
    assert len(after) > len(before)


# T7 -----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "args",
    [
        ("--section", "nope", "--text", "t"),
        ("--section", "human-decision", "--text", "t", "-n", "design/design"),
        ("--section", "events", "--text", "t"),
        ("--section", "plan-record", "--text", "t"),
        ("--section", "background"),  # no text handled by typer; see below
        ("--section", "background", "--text", "t", "--scope", "plan"),
        ("--section", "open-question", "--text", "t"),
        ("--section", "open-question", "--scope", "change", "--text", "t", "-p", "001"),
        ("--section", "open-question", "--scope", "change", "--text", "t", "-n", "design/design"),
        ("--section", "background", "--text", "t", "--actor", "HUMAN", "--by", "x"),
        ("--section", "decision", "--text", "t"),
        ("--section", "decision", "--text", "t", "--actor", "HUMAN"),
        ("--section", "decision", "--text", "t", "--by", "用户"),
        ("--section", "decision", "--text", "t", "--actor", "human", "--by", "用户"),
        ("--section", "decision", "--text", "t", "--actor", "OTHER", "--by", "用户"),
        ("--section", "assumption", "--text", "t"),
        ("--section", "deviation", "--text", "t"),
        ("--section", "rework", "--text", "t"),
        ("--section", "assumption", "--text", "t", "-n", "design/design", "--actor", "MODEL"),
    ],
)
def test_invalid_parameters_are_rejected_and_nothing_is_written(tmp_path: Path, args: tuple):
    home = draft_home(tmp_path)
    before = (digest(change_state(home)), digest(plan_state(home)))
    code, result = add(home, *args)
    assert code != 0
    if result:
        assert result["error"] == "workflow_invalid"
    assert (digest(change_state(home)), digest(plan_state(home))) == before


def test_only_add_exists_under_state():
    from typer.testing import CliRunner

    from loopspec.cli import app

    runner = CliRunner()
    for verb in ("resolve", "supersede", "verify"):
        assert runner.invoke(app, ["state", verb]).exit_code == 2
    assert runner.invoke(app, ["state", "add", "--help"]).exit_code == 0


# T8 -----------------------------------------------------------------------------------


def test_newlines_and_control_characters_are_normalised_when_the_rest_is_valid(tmp_path: Path):
    home = draft_home(tmp_path)
    code, result = add(
        home, "--section", "decision", "--actor", "MODEL", "--by", "B\nE\x07",
        "--text", "第一行\r\n第二行\t\x00尾",
    )  # fmt: skip
    assert code == 0, result
    assert result["line"].endswith("[MODEL: B E] 第一行 第二行 尾")
    assert "\x07" not in change_state(home).read_text()
    assert result["line"] in change_state(home).read_text().splitlines()


@pytest.mark.parametrize(
    "text",
    ["", "   \n\t ", "\x07\x00", "x" * 1001, "<!-- 注释", "文字 <!-- 隐藏", "结束 -->", "a-->b"],
)
def test_invalid_text_is_rejected_for_every_text_field(tmp_path: Path, text: str):
    home = draft_home(tmp_path)
    before = digest(change_state(home))
    code, result = add(
        home, "--section", "decision", "--actor", "HUMAN", "--by", "用户", "--text", text
    )
    assert code == 1 and result["error"] == "workflow_invalid"
    code, result = add(
        home, "--section", "decision", "--actor", "HUMAN", "--by", text, "--text", "合法"
    )
    assert code == 1 and result["error"] == "workflow_invalid"
    assert digest(change_state(home)) == before


def test_text_and_by_length_boundaries(tmp_path: Path):
    home = draft_home(tmp_path)
    code, _ = add(home, "--section", "background", "--text", "x" * 1000)
    assert code == 0
    code, _ = add(
        home, "--section", "decision", "--actor", "HUMAN", "--by", "中" * 64, "--text", "t"
    )
    assert code == 0
    code, _ = add(
        home, "--section", "decision", "--actor", "HUMAN", "--by", "中" * 65, "--text", "t"
    )
    assert code == 1


# T9 -----------------------------------------------------------------------------------


def test_heading_like_content_stays_inside_its_bullet(tmp_path: Path):
    home = draft_home(tmp_path)
    for text in ("## 事件", "## 背景", "# 标题"):
        code, result = add(home, "--section", "background", "--text", text)
        assert code == 0, result
        assert result["line"].startswith("- ") and result["line"].endswith(text)
    assert add(home, "--section", "background", "--text", "再追加")[0] == 0
    assert headings(change_state(home).read_text()) == headings(notes.change_template())
    assert len(section_lines(change_state(home), "背景")) == 4


# T10 ----------------------------------------------------------------------------------


def test_missing_or_duplicate_headings_and_missing_file_fail_without_changes(tmp_path: Path):
    home = draft_home(tmp_path)
    original = change_state(home).read_text()
    change_state(home).write_text(original.replace("## 背景", "## 其他"))
    before = digest(change_state(home))
    code, result = add(home, "--section", "background", "--text", "t")
    assert code == 1 and result["error"] == "state_section_missing"
    assert digest(change_state(home)) == before
    change_state(home).write_text(original + "\n## 背景\n")
    before = digest(change_state(home))
    code, result = add(home, "--section", "background", "--text", "t")
    assert code == 1 and result["error"] == "state_section_ambiguous"
    assert digest(change_state(home)) == before
    change_state(home).unlink()
    code, result = add(home, "--section", "background", "--text", "t")
    assert code == 1 and result["error"] == "state_section_missing"
    assert not change_state(home).exists()


def test_oversized_state_file_is_refused_not_truncated(tmp_path: Path):
    home = draft_home(tmp_path)
    change_state(home).write_bytes("## 背景\n".encode() + b"x" * MAX_FILE_BYTES)
    before = digest(change_state(home))
    code, result = add(home, "--section", "background", "--text", "t")
    assert code == 1 and result["error"] == "resource_limit"
    assert digest(change_state(home)) == before


# T11 ----------------------------------------------------------------------------------


def test_unknown_change_and_unsafe_names_fail(tmp_path: Path):
    home = project(tmp_path)
    code, result = invoke(
        home, "state", "add", "-c", "NOPE", "--section", "background", "--text", "t"
    )
    assert code == 1 and result["error"]
    code, result = invoke(
        home, "state", "add", "-c", "../x", "--section", "background", "--text", "t"
    )
    assert code == 1 and result["error"] == "invalid_change_name"
    new_change(home)
    code, result = add(home, "--section", "assumption", "-p", "../1", "-n", "x", "--text", "t")
    assert code == 1 and result["error"] in ("invalid_plan", "workflow_invalid")


# T12 ----------------------------------------------------------------------------------


def test_actor_and_node_validation(tmp_path: Path):
    home = draft_home(tmp_path)
    for actor, by in (("HUMAN", "张 三"), ("MODEL", "后端 Agent")):
        code, result = add(
            home, "--section", "decision", "--actor", actor, "--by", by, "--text", "t"
        )
        assert code == 0, result
        assert f"[{actor}: {by}]" in result["line"]
    assert add(home, "--section", "assumption", "-n", "design/design", "--text", "t")[0] == 0
    for node in ("design", "nope", "../etc", "design/design/extra"):
        before = digest(plan_state(home))
        code, result = add(home, "--section", "assumption", "-n", node, "--text", "t")
        assert code == 1 and result["error"] == "workflow_invalid", node
        assert digest(plan_state(home)) == before
    code, result = add(home, "--section", "rework", "-n", "design/design", "--text", "t")
    assert code == 1 and result["error"] == "workflow_invalid"


def test_by_and_node_never_become_part_of_a_path(tmp_path: Path):
    home = draft_home(tmp_path)
    code, result = add(
        home, "--section", "decision", "--actor", "HUMAN", "--by", "../../evil", "--text", "t"
    )
    assert code == 0 and result["path"] == str(change_state(home))
    assert not (tmp_path / "evil").exists() and not (home.parent / "evil").exists()


# T13 ----------------------------------------------------------------------------------


def test_links_and_non_regular_state_files_are_refused(tmp_path: Path):
    home = draft_home(tmp_path)
    outside = tmp_path / "outside.md"
    outside.write_text("## 背景\n\noutside\n")
    original = change_state(home).read_bytes()
    change_state(home).unlink()
    change_state(home).symlink_to(outside)
    code, result = add(home, "--section", "background", "--text", "t")
    assert code == 1 and result["error"] == "unsafe_path"
    change_state(home).unlink()
    os.link(outside, change_state(home))
    code, result = add(home, "--section", "background", "--text", "t")
    assert code == 1 and result["error"] == "unsafe_path"
    change_state(home).unlink()
    change_state(home).mkdir()
    code, result = add(home, "--section", "background", "--text", "t")
    assert code == 1 and result["error"] == "unsafe_path"
    change_state(home).rmdir()
    change_state(home).write_bytes(original)
    assert outside.read_text() == "## 背景\n\noutside\n"


def test_read_regular_file_limits_and_identity(tmp_path: Path):
    path = tmp_path / "f.md"
    assert read_regular_file(tmp_path, "f.md") is None
    path.write_bytes(b"x" * 10)
    data, identity = read_regular_file(tmp_path, "f.md", limit=10) or (b"", ())
    assert data == b"x" * 10
    with pytest.raises(WorkflowError) as exc:
        read_regular_file(tmp_path, "f.md", limit=9)
    assert exc.value.code == "resource_limit"
    ensure_file_identity(tmp_path, "f.md", identity)
    path.write_bytes(b"changed!!!")
    with pytest.raises(WorkflowError) as exc:
        ensure_file_identity(tmp_path, "f.md", identity)
    assert exc.value.code == "concurrent_source_change"
    path.unlink()
    with pytest.raises(WorkflowError) as exc:
        ensure_file_identity(tmp_path, "f.md", identity)
    assert exc.value.code == "concurrent_path_change"


def test_file_replaced_between_read_and_write_is_not_overwritten(tmp_path: Path, monkeypatch):
    home = draft_home(tmp_path)
    real = notes.insert_entry

    def replace_then_insert(data: bytes, title: str, entry: str) -> bytes:
        change_state(home).write_bytes("## 背景\n\n手工写入\n".encode())
        return real(data, title, entry)

    monkeypatch.setattr(notes, "insert_entry", replace_then_insert)
    code, result = add(home, "--section", "background", "--text", "t")
    assert code == 1 and result["error"] == "concurrent_source_change"
    assert change_state(home).read_bytes() == "## 背景\n\n手工写入\n".encode()


# T14 ----------------------------------------------------------------------------------


def bugfix_home(tmp_path: Path) -> Path:
    home = project(tmp_path)
    create_approved(home, BUGFIX_FLOW)
    return home


def fail_and_rollback(home: Path, tmp_path: Path, content: str) -> dict:
    (tmp_path / "backend/code.py").write_text(content)
    run_until(home, "qa/test")
    fail_gate(home, "qa/test")
    code, result = invoke(home, "plan", "rollback", "-c", CHANGE, "-p", "001")
    assert code == 0, result
    return result


def test_rework_round_and_rollback_seq_come_from_committed_rollbacks(tmp_path: Path):
    home = bugfix_home(tmp_path)
    code, result = add(home, "--section", "rework", "-n", "qa/test", "--text", "还没返工")
    assert code == 1 and result["error"] == "state_rework_no_rollback"
    first = fail_and_rollback(home, tmp_path, "one\n")
    code, result = add(home, "--section", "rework", "-n", "qa/test", "--text", "缺陷 A")
    assert code == 0, result
    assert result["line"].endswith(f"[qa/test] attempt 1（rollback #{first['attempt']}）：缺陷 A")
    second = fail_and_rollback(home, tmp_path, "two\n")
    assert second["attempt"] > first["attempt"]
    code, result = add(home, "--section", "rework", "-n", "qa/test", "--text", "缺陷 B")
    assert code == 0, result
    assert result["line"].endswith(f"[qa/test] attempt 2（rollback #{second['attempt']}）：缺陷 B")
    plan = plan_state(home).read_text()
    assert "attempt 1（rollback #" in plan and "attempt 2（rollback #" in plan
    code, result = add(home, "--section", "rework", "-n", "be/code/implement", "--text", "t")
    assert code == 1 and result["error"] == "workflow_invalid"


def test_rework_on_a_draft_without_attempts_reports_no_rollback(tmp_path: Path):
    home = project(tmp_path)
    new_change(home)
    create_draft(home, BUGFIX_FLOW)
    code, result = add(home, "--section", "rework", "-n", "qa/test", "--text", "t")
    assert code == 1 and result["error"] == "state_rework_no_rollback"
    assert not (home / "changes" / CHANGE / "plans" / "001" / ".attempts").exists()


def test_rework_numbers_with_revisions_and_several_gates_interleaved(monkeypatch):
    records = [
        SimpleNamespace(seq=1, kind="rollback", gate="A"),
        SimpleNamespace(seq=2, kind="revision", gate=None),
        SimpleNamespace(seq=3, kind="rollback", gate="B"),
        SimpleNamespace(seq=4, kind="rollback", gate="A"),
    ]
    monkeypatch.setattr(notes, "committed_records", lambda loaded: records)
    assert notes._rework_numbers(SimpleNamespace(), "A") == (2, 4)
    assert notes._rework_numbers(SimpleNamespace(), "B") == (1, 3)
    with pytest.raises(WorkflowError) as exc:
        notes._rework_numbers(SimpleNamespace(), "C")
    assert exc.value.code == "state_rework_no_rollback"
    # the round is not the directory number
    assert notes._rework_numbers(SimpleNamespace(), "A")[0] != 4


def test_callers_cannot_supply_the_round_or_seq(tmp_path: Path):
    home = bugfix_home(tmp_path)
    fail_and_rollback(home, tmp_path, "one\n")
    for flag in ("--attempt", "--seq", "--round"):
        code, _ = add(home, "--section", "rework", "-n", "qa/test", "--text", "t", flag, "9")
        assert code == 2


# T15 / T16 ----------------------------------------------------------------------------


def hold_lock(home: Path):
    fd = os.open(home / "changes" / CHANGE / "plans" / ".write.lock", os.O_RDWR | os.O_CREAT, 0o600)
    fcntl.flock(fd, fcntl.LOCK_EX)
    return fd


def test_lock_contention_returns_concurrent_write_without_writing(tmp_path: Path):
    home = draft_home(tmp_path)
    before = digest(change_state(home))
    fd = hold_lock(home)
    try:
        code, result = add(home, "--section", "background", "--text", "t")
        assert code == 1 and result["error"] == "concurrent_write"
        assert digest(change_state(home)) == before
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)
    code, result = add(home, "--section", "background", "--text", "t")
    assert code == 0, result


def test_state_add_and_lifecycle_commands_share_the_change_lock(tmp_path: Path):
    home = draft_home(tmp_path)
    shown = invoke(home, "plan", "show", "-c", CHANGE, "-p", "001")[1]
    ctx_root = home / "changes" / CHANGE
    with write_lock(ctx_root):
        code, result = invoke(
            home, "plan", "approve", "-c", CHANGE, "-p", "001", "--digest", shown["meta"]["digest"]
        )
        assert code == 1 and result["error"] == "concurrent_write"
        code, result = add(home, "--section", "background", "--text", "t")
        assert code == 1 and result["error"] == "concurrent_write"
    approve(home, "001")
    assert add(home, "--section", "background", "--text", "retry")[0] == 0
    events = [line for line in plan_state(home).read_text().splitlines() if "已批准" in line]
    assert len(events) == 1
    assert any("retry" in line for line in change_state(home).read_text().splitlines())


# T17 / T18 ----------------------------------------------------------------------------


def instructions(home: Path, node: str) -> dict:
    code, result = invoke(home, "node", "instructions", "-c", CHANGE, "-n", node)
    assert code == 0, result
    return result


def test_every_leaf_gets_a_state_protocol_and_gates_add_rework(tmp_path: Path):
    home = bugfix_home(tmp_path)
    plain = instructions(home, "requirements/proposal")["stateProtocol"]
    keys = [(item["key"], item["scope"]) for item in plain["sections"]]
    assert keys == [
        ("decision", "change"), ("open-question", "change"), ("assumption", "plan"),
        ("deviation", "plan"), ("open-question", "plan"),
    ]  # fmt: skip
    assert plain["context"] == {
        "changeName": CHANGE, "plan": "001", "node": "requirements/proposal"
    }  # fmt: skip
    for item in plain["sections"]:
        assert {"when", "contentBoundary", "format", "required", "optional", "command"} <= set(item)
        command = item["command"]
        assert command.startswith(f"loopspec state add -c {CHANGE} --section {item['key']}")
        if item["scope"] == "change":
            assert " -p " not in command and " -n " not in command
        else:
            assert " -p 001 -n requirements/proposal " in command
        if item["key"] == "open-question":
            assert f"--scope {item['scope']}" in command
    decision = next(item for item in plain["sections"] if item["key"] == "decision")
    assert "--actor <HUMAN或MODEL> --by <实际主体>" in decision["command"]
    assert "--scope" not in decision["command"]
    assert "rework" not in {item["key"] for item in plain["sections"]}
    run_until(home, "qa/test")
    gate = instructions(home, "qa/test")
    assert ("rework", "plan") in [(i["key"], i["scope"]) for i in gate["stateProtocol"]["sections"]]


def test_protocol_commands_are_accepted_by_the_command_they_describe(tmp_path: Path):
    home = bugfix_home(tmp_path)
    for item in instructions(home, "requirements/proposal")["stateProtocol"]["sections"]:
        args = item["command"].split()[2:]  # from "add" on
        args = args[: args.index("--text")] + ["--text", "协议示例"]
        args = [{"<HUMAN或MODEL>": "MODEL", "<实际主体>": "BE"}.get(token, token) for token in args]
        code, result = invoke(home, "state", *args)
        assert code == 0, (item["command"], result)


def test_protocol_text_comes_from_the_registry(monkeypatch):
    spec = notes.SECTIONS["assumption"].scopes["plan"]
    changed = notes.ScopeSpec(
        boundary="新边界", when="新时机", format="新格式", hint=spec.hint,
        required=spec.required, optional=spec.optional, text_hint=spec.text_hint,
    )  # fmt: skip
    monkeypatch.setitem(
        notes.SECTIONS,
        "assumption",
        notes.Section("assumption", "假设", "agent", {"plan": changed}),
    )
    item = next(
        entry
        for entry in notes.state_protocol("c", "001", "n", gate=False)["sections"]
        if entry["key"] == "assumption"
    )
    assert (item["contentBoundary"], item["when"], item["format"]) == ("新边界", "新时机", "新格式")
    assert "## 假设" in notes.plan_template("001")


# T20 ----------------------------------------------------------------------------------


def test_status_text_points_to_state_add_and_old_files_still_display(tmp_path: Path):
    home = draft_home(tmp_path)
    out = runner.invoke(app, ["change", "status", CHANGE, "--home", str(home)]).stdout
    assert "loopspec state add" in out and "edit the file named" not in out
    change_state(home).write_text("# 需求记录\n\n## 关键决策\n\n旧模板内容 OLD-TEMPLATE\n")
    out = runner.invoke(app, ["change", "status", CHANGE, "--home", str(home)]).stdout
    assert "OLD-TEMPLATE" in out
    code, result = add(
        home, "--section", "decision", "--actor", "HUMAN", "--by", "用户", "--text", "t"
    )
    assert code == 1 and result["error"] == "state_section_missing"
    assert "OLD-TEMPLATE" in change_state(home).read_text()


# T21 ----------------------------------------------------------------------------------


def test_open_question_routes_by_explicit_scope(tmp_path: Path):
    home = draft_home(tmp_path)
    code, result = add(home, "--section", "open-question", "--text", "没有 scope")
    assert code == 1 and result["error"] == "workflow_invalid"
    code, result = add(home, "--section", "open-question", "--scope", "change", "--text", "跨 Plan")
    assert code == 0 and result["scope"] == "change" and result["plan"] is None
    assert section_lines(change_state(home), "待解决问题") == [result["line"]]
    code, result = add(
        home, "--section", "open-question", "--scope", "plan", "-p", "001", "--text", "无节点"
    )
    assert code == 0 and result["plan"] == "001" and "[" not in result["line"]
    code, result = add(
        home,
        "--section",
        "open-question",
        "--scope",
        "plan",
        "-n",
        "design/design",
        "--text",
        "有节点",  # fmt: skip
    )
    assert code == 0 and "[design/design]" in result["line"]
    assert len(section_lines(plan_state(home), "待解决问题")) == 2
    first = section_lines(change_state(home), "待解决问题")[0]
    resolved = add(
        home, "--section", "open-question", "--scope", "change", "--text", "解决：跨 Plan"
    )
    assert resolved[0] == 0
    assert section_lines(change_state(home), "待解决问题")[0] == first
    code, result = add(
        home, "--section", "open-question", "--scope", "change", "-p", "001", "--text", "t"
    )
    assert code == 1 and result["error"] == "workflow_invalid"


# T19 / T22 ----------------------------------------------------------------------------


@pytest.mark.parametrize("lang", ["en", "zh"])
def test_docs_describe_the_unified_state_protocol(lang: str):
    docs = Path(__file__).resolve().parent.parent / "docs" / lang
    reference = (docs / "cli-reference.md").read_text()
    protocol = (docs / "agent-protocol.md").read_text()
    overview = (docs / "overview.md").read_text()
    for text in ("## loopspec state add", "stateProtocol", "state_section_missing", "--actor"):
        assert text in reference, text
    for text in ("MODEL", "HUMAN", "open-question", "concurrent_write", "state_section_ambiguous"):
        assert text in protocol, text
    for text in ("state add", "decision", "assumption", "deviation", "rework"):
        assert text in overview, text
    for text in ("human-decision", "--question", "--answer"):
        assert text not in reference + protocol + overview, text
