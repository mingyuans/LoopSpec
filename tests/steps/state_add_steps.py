"""Steps for `loopspec state add`."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import pytest
from pytest_bdd import given, parsers, then, when

from tests.conftest import ChangeLock, CliOutcome, LastCall
from tests.steps.common import outcome_of
from tests.workflow_helpers import CHANGE, fail_gate, run_until

RunCli = Callable[..., CliOutcome]


def change_state(home: Path) -> Path:
    return home / "changes" / CHANGE / "state.md"


def plan_state(home: Path) -> Path:
    return home / "changes" / CHANGE / "plans" / "001" / "state.md"


def fingerprint(home: Path) -> dict[str, str]:
    return {
        str(path): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in (change_state(home), plan_state(home))
    }


def add(
    run_cli: RunCli,
    last_call: LastCall,
    file_fingerprints: dict[str, str],
    home: Path,
    *options: str,
    text: str,
) -> CliOutcome:
    """Run `state add`, remembering the files' state before and the call itself."""
    file_fingerprints.clear()
    file_fingerprints.update(fingerprint(home))
    args = ("state", "add", "-c", CHANGE, *options, "--text", text)
    last_call.args, last_call.text = args, text
    last_call.outcome = run_cli(*args)
    return last_call.outcome


# --- decisions ------------------------------------------------------------------------


@when(parsers.parse('用户记录一条由 "{actor}" 做出、决策人为 "{name}" 的决策'))
def record_decision(run_cli, last_call, file_fingerprints, home, actor: str, name: str) -> None:
    add(
        run_cli, last_call, file_fingerprints, home,
        "--section", "decision", "--actor", actor, "--by", name,
        text="采用方案 A，理由见设计",
    )  # fmt: skip


@then(parsers.parse('Change 状态中这条决策带有标记 "{tag}"'))
def decision_is_tagged(home: Path, last_call: LastCall, tag: str) -> None:
    lines = change_state(home).read_text().splitlines()
    assert any(tag in line and last_call.text in line for line in lines), tag


# --- open questions -------------------------------------------------------------------


@when("不指定范围添加一个待定问题")
def question_without_scope(run_cli, last_call, file_fingerprints, home) -> None:
    add(run_cli, last_call, file_fingerprints, home, "--section", "open-question", text="没有范围")


@when(parsers.re(r'以范围 "(?P<scope>[^"]+)" 添加一个待定问题'))
def question_with_scope(run_cli, last_call, file_fingerprints, home, scope: str) -> None:
    add(
        run_cli, last_call, file_fingerprints, home,
        "--section", "open-question", "--scope", scope,
        text=f"{scope} 层的问题",
    )  # fmt: skip


@when(parsers.re(r'以范围 "(?P<scope>[^"]+)"、节点 "(?P<node>[^"]+)" 添加一个待定问题'))
def question_with_scope_and_node(
    run_cli, last_call, file_fingerprints, home, scope: str, node: str
) -> None:
    add(
        run_cli, last_call, file_fingerprints, home,
        "--section", "open-question", "--scope", scope, "-n", node,
        text=f"{scope} 层、节点 {node} 的问题",
    )  # fmt: skip


@then("该条目没有节点标记")
def entry_has_no_node_tag(last_call: LastCall) -> None:
    assert "[" not in outcome_of(last_call).data["line"]


@then(parsers.parse('该条目带有节点标记 "{tag}"'))
def entry_has_node_tag(last_call: LastCall, tag: str) -> None:
    assert tag in outcome_of(last_call).data["line"]


@then("没有任何状态文件变化")
def nothing_changed(home: Path, file_fingerprints: dict[str, str]) -> None:
    assert fingerprint(home) == file_fingerprints


@then("它只出现在 Change 状态中")
def only_in_change(home: Path, last_call: LastCall) -> None:
    assert last_call.text in change_state(home).read_text()
    assert last_call.text not in plan_state(home).read_text()


@then("它只出现在 Plan 状态中")
def only_in_plan(home: Path, last_call: LastCall) -> None:
    assert last_call.text in plan_state(home).read_text()
    assert last_call.text not in change_state(home).read_text()


# --- corrections ----------------------------------------------------------------------


@given(parsers.parse('已记录一条笔记 "{text}"'))
def recorded_note(run_cli, last_call, file_fingerprints, home, recorded_lines, text: str) -> None:
    outcome = add(run_cli, last_call, file_fingerprints, home, "--section", "background", text=text)
    assert outcome.code == 0, outcome.data
    recorded_lines.append(outcome.data["line"])


@when("追加一条更正笔记")
def correcting_note(run_cli, last_call, file_fingerprints, home, recorded_lines) -> None:
    outcome = add(
        run_cli, last_call, file_fingerprints, home, "--section", "background",
        text="更正：第一版作废，以此为准",
    )  # fmt: skip
    if outcome.code == 0:
        recorded_lines.append(outcome.data["line"])


@then("两条笔记都在且顺序不变")
def both_notes_in_order(home: Path, recorded_lines: list[str]) -> None:
    original, correction = recorded_lines
    lines = change_state(home).read_text().splitlines()
    assert original in lines and correction in lines
    assert lines.index(original) < lines.index(correction)


# --- CRLF -----------------------------------------------------------------------------


@pytest.fixture
def crlf_before(home: Path) -> dict[str, bytes]:
    """The Change state as it was just before the command, filled in by the CRLF step."""
    return {}


@given("Change 状态使用 CRLF 换行")
def state_uses_crlf(home: Path, crlf_before: dict[str, bytes]) -> None:
    converted = change_state(home).read_bytes().replace(b"\n", b"\r\n")
    change_state(home).write_bytes(converted)
    crlf_before["bytes"] = converted


@when("记录一条参考")
def reference_recorded(run_cli, last_call, file_fingerprints, home) -> None:
    add(run_cli, last_call, file_fingerprints, home, "--section", "reference", text="参考 R")


@then("文件中所有换行符仍是 CRLF")
def all_crlf(home: Path) -> None:
    data = change_state(home).read_bytes()
    assert b"\r\n" in data and data.count(b"\n") == data.count(b"\r\n")


@then("目标小节前后的文本逐字节一致")
def surroundings_identical(home: Path, crlf_before: dict[str, bytes]) -> None:
    before, after = crlf_before["bytes"], change_state(home).read_bytes()
    target, tail = "## 参考".encode(), "## Plan 记录".encode()
    assert after[: after.index(target)] == before[: before.index(target)]
    assert after[after.index(tail) :] == before[before.index(tail) :]


# --- lock -----------------------------------------------------------------------------


@given("另一个命令持有 Change 写锁")
def lock_is_held(change_lock: ChangeLock) -> None:
    change_lock.acquire()


@when("添加一条笔记")
def note_added(run_cli, last_call, file_fingerprints, home) -> None:
    add(run_cli, last_call, file_fingerprints, home, "--section", "background", text="重试笔记")


@when("释放写锁并原样重试同一命令")
def retry_after_release(run_cli, last_call: LastCall, change_lock: ChangeLock) -> None:
    change_lock.release()
    last_call.outcome = run_cli(*last_call.args)


@then("笔记已被记录")
def note_recorded(home: Path, last_call: LastCall) -> None:
    outcome = outcome_of(last_call)
    assert outcome.code == 0, outcome.data
    assert last_call.text in change_state(home).read_text()


# --- rework ---------------------------------------------------------------------------


@given(parsers.parse('"{gate}" Gate 失败并回滚'))
def gate_fails_and_rolls_back(run_cli, home, tmp_path, rollback_log, gate: str) -> None:
    (tmp_path / "backend/code.py").write_text(f"round {len(rollback_log) + 1}\n")
    run_until(home, gate)
    fail_gate(home, gate)
    outcome = run_cli("plan", "rollback", "-c", CHANGE, "-p", "001")
    assert outcome.code == 0, outcome.data
    rollback_log.append(outcome.data["attempt"])


@when(parsers.parse('尝试为 "{gate}" 记录返工笔记'))
def rework_attempted(run_cli, last_call, file_fingerprints, home, gate: str) -> None:
    add(
        run_cli,
        last_call,
        file_fingerprints,
        home,
        "--section",
        "rework",
        "-n",
        gate,
        text="尚无返工",
    )


@given(parsers.parse('已为 "{gate}" 记录一条返工笔记'))
def rework_recorded(run_cli, last_call, file_fingerprints, home, recorded_lines, gate: str) -> None:
    outcome = add(
        run_cli, last_call, file_fingerprints, home, "--section", "rework", "-n", gate,
        text=f"第 {len(recorded_lines) + 1} 次认识",
    )  # fmt: skip
    assert outcome.code == 0, outcome.data
    recorded_lines.append(outcome.data["line"])


@then(parsers.parse('第一条返工笔记写明 "{label}" 及其回滚编号'))
def first_rework(recorded_lines: list[str], rollback_log: list[int], label: str) -> None:
    assert f"{label}（rollback #{rollback_log[0]}）" in recorded_lines[0]


@then(parsers.parse('第二条返工笔记写明 "{label}" 及其回滚编号'))
def second_rework(recorded_lines: list[str], rollback_log: list[int], label: str) -> None:
    assert f"{label}（rollback #{rollback_log[1]}）" in recorded_lines[1]


# --- real process smoke ---------------------------------------------------------------


@when(parsers.parse('已安装的 "{command}" 可执行文件记录一条决策'))
def installed_executable(home: Path, tmp_path: Path, last_call: LastCall, command: str) -> None:
    # Only the executable installed next to this interpreter counts; never one found on PATH.
    executable = Path(sys.executable).parent / command
    if not executable.is_file():
        pytest.skip(f"{command} is not installed in {executable.parent}; run `uv sync`")
    last_call.text = "子进程冒烟决策"
    completed = subprocess.run(  # noqa: S603 - fixed argv, no shell
        [str(executable), "state", "add", "-c", CHANGE, "--section", "decision",
         "--actor", "MODEL", "--by", "BE", "--text", last_call.text, "--home", str(home)],
        cwd=tmp_path, capture_output=True, text=True, timeout=120, check=False,
    )  # fmt: skip
    last_call.outcome = CliOutcome(completed.returncode, json.loads(completed.stdout or "{}"))


@then("退出码为 0 且该行出现在 Change 状态中")
def smoke_result(home: Path, last_call: LastCall) -> None:
    outcome = outcome_of(last_call)
    assert outcome.code == 0, outcome.data
    assert outcome.data["line"] in change_state(home).read_text().splitlines()
