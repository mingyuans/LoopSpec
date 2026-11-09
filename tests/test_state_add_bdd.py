"""BDD scenarios for `loopspec state add`; the steps live here, registered explicitly."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from tests.conftest import ChangeLock, CliOutcome, LastCall
from tests.workflow_helpers import BUGFIX_FLOW, CHANGE, create_approved, fail_gate, run_until

scenarios("features/state_add.feature")

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


# --- Background -----------------------------------------------------------------------


@given("an approved plan in an isolated project")
def approved_plan(home: Path) -> None:
    create_approved(home, BUGFIX_FLOW)


# --- decisions ------------------------------------------------------------------------


@when(parsers.parse('the user records a decision by "{actor}" named "{name}"'))
def record_decision(run_cli, last_call, file_fingerprints, home, actor: str, name: str) -> None:
    outcome = add(
        run_cli, last_call, file_fingerprints, home,
        "--section", "decision", "--actor", actor, "--by", name,
        text="采用方案 A，理由见设计",
    )  # fmt: skip
    assert outcome.code == 0, outcome.data


@then(parsers.parse('the Change state lists that decision tagged "{tag}"'))
def decision_is_tagged(home: Path, last_call: LastCall, tag: str) -> None:
    lines = change_state(home).read_text().splitlines()
    assert any(tag in line and last_call.text in line for line in lines), tag


# --- open questions -------------------------------------------------------------------


@when("an open question is added without a scope")
def question_without_scope(run_cli, last_call, file_fingerprints, home) -> None:
    add(run_cli, last_call, file_fingerprints, home, "--section", "open-question", text="没有范围")


@when(parsers.parse('an open question is added with scope "{scope}"'))
def question_with_scope(run_cli, last_call, file_fingerprints, home, scope: str) -> None:
    outcome = add(
        run_cli, last_call, file_fingerprints, home,
        "--section", "open-question", "--scope", scope,
        text=f"{scope} 层的问题",
    )  # fmt: skip
    assert outcome.code == 0, outcome.data


@when(parsers.parse('an open question is added with scope "{scope}" and node "{node}"'))
def question_with_scope_and_node(
    run_cli, last_call, file_fingerprints, home, scope: str, node: str
) -> None:
    outcome = add(
        run_cli, last_call, file_fingerprints, home,
        "--section", "open-question", "--scope", scope, "-n", node,
        text=f"{scope} 层、节点 {node} 的问题",
    )  # fmt: skip
    assert outcome.code == 0, outcome.data


@then("the entry has no node tag")
def entry_has_no_node_tag(last_call: LastCall) -> None:
    assert last_call.outcome is not None
    assert "[" not in last_call.outcome.data["line"]


@then(parsers.parse('the entry carries the node tag "{tag}"'))
def entry_has_node_tag(last_call: LastCall, tag: str) -> None:
    assert last_call.outcome is not None
    assert tag in last_call.outcome.data["line"]


@then(parsers.parse('the command fails with "{error}"'))
def command_fails(last_call: LastCall, error: str) -> None:
    assert last_call.outcome is not None
    assert last_call.outcome.code == 1 and last_call.outcome.data["error"] == error


@then("no state file changed")
def nothing_changed(home: Path, file_fingerprints: dict[str, str]) -> None:
    assert fingerprint(home) == file_fingerprints


@then("it appears in the Change state only")
def only_in_change(home: Path, last_call: LastCall) -> None:
    assert last_call.text in change_state(home).read_text()
    assert last_call.text not in plan_state(home).read_text()


@then("it appears in the Plan state only")
def only_in_plan(home: Path, last_call: LastCall) -> None:
    assert last_call.text in plan_state(home).read_text()
    assert last_call.text not in change_state(home).read_text()


# --- corrections ----------------------------------------------------------------------


@given(parsers.parse('a recorded note "{text}"'))
def recorded_note(run_cli, last_call, file_fingerprints, home, recorded_lines, text: str) -> None:
    outcome = add(run_cli, last_call, file_fingerprints, home, "--section", "background", text=text)
    assert outcome.code == 0, outcome.data
    recorded_lines.append(outcome.data["line"])


@when("a correcting note is added")
def correcting_note(run_cli, last_call, file_fingerprints, home, recorded_lines) -> None:
    outcome = add(
        run_cli, last_call, file_fingerprints, home, "--section", "background",
        text="更正：第一版作废，以此为准",
    )  # fmt: skip
    assert outcome.code == 0, outcome.data
    recorded_lines.append(outcome.data["line"])


@then("both notes are present in order")
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


@given("the Change state uses CRLF line endings")
def state_uses_crlf(home: Path, crlf_before: dict[str, bytes]) -> None:
    converted = change_state(home).read_bytes().replace(b"\n", b"\r\n")
    change_state(home).write_bytes(converted)
    crlf_before["bytes"] = converted


@when("a reference is recorded")
def reference_recorded(run_cli, last_call, file_fingerprints, home) -> None:
    outcome = add(
        run_cli, last_call, file_fingerprints, home, "--section", "reference", text="参考 R"
    )
    assert outcome.code == 0, outcome.data


@then("every line ending in the file is still CRLF")
def all_crlf(home: Path) -> None:
    data = change_state(home).read_bytes()
    assert b"\r\n" in data and data.count(b"\n") == data.count(b"\r\n")


@then("the text around the target section is byte-identical")
def surroundings_identical(home: Path, crlf_before: dict[str, bytes]) -> None:
    before, after = crlf_before["bytes"], change_state(home).read_bytes()
    target, tail = "## 参考".encode(), "## Plan 记录".encode()
    assert after[: after.index(target)] == before[: before.index(target)]
    assert after[after.index(tail) :] == before[before.index(tail) :]


# --- lock -----------------------------------------------------------------------------


@given("another command holds the Change write lock")
def lock_is_held(change_lock: ChangeLock) -> None:
    change_lock.acquire()


@when("a note is added")
def note_added(run_cli, last_call, file_fingerprints, home) -> None:
    add(run_cli, last_call, file_fingerprints, home, "--section", "background", text="重试笔记")


@when("the lock is released and the same command is retried")
def retry_after_release(run_cli, last_call: LastCall, change_lock: ChangeLock) -> None:
    change_lock.release()
    last_call.outcome = run_cli(*last_call.args)


@then("the note is recorded")
def note_recorded(home: Path, last_call: LastCall) -> None:
    assert last_call.outcome is not None and last_call.outcome.code == 0, last_call.outcome
    assert last_call.text in change_state(home).read_text()


# --- rework ---------------------------------------------------------------------------


@given(parsers.parse('the "{gate}" Gate fails and is rolled back'))
@when(parsers.parse('the "{gate}" Gate fails and is rolled back'))
def gate_fails_and_rolls_back(run_cli, home, tmp_path, rollback_log, gate: str) -> None:
    (tmp_path / "backend/code.py").write_text(f"round {len(rollback_log) + 1}\n")
    run_until(home, gate)
    fail_gate(home, gate)
    outcome = run_cli("plan", "rollback", "-c", CHANGE, "-p", "001")
    assert outcome.code == 0, outcome.data
    rollback_log.append(outcome.data["attempt"])


@when(parsers.parse('a rework note is attempted for "{gate}"'))
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


@when(parsers.parse('a rework note is recorded for "{gate}"'))
def rework_recorded(run_cli, last_call, file_fingerprints, home, recorded_lines, gate: str) -> None:
    outcome = add(
        run_cli, last_call, file_fingerprints, home, "--section", "rework", "-n", gate,
        text=f"第 {len(recorded_lines) + 1} 次认识",
    )  # fmt: skip
    assert outcome.code == 0, outcome.data
    recorded_lines.append(outcome.data["line"])


@then(parsers.parse('the first rework note reads "{label}" with its rollback number'))
def first_rework(recorded_lines: list[str], rollback_log: list[int], label: str) -> None:
    assert f"{label}（rollback #{rollback_log[0]}）" in recorded_lines[0]


@then(parsers.parse('the second rework note reads "{label}" with its rollback number'))
def second_rework(recorded_lines: list[str], rollback_log: list[int], label: str) -> None:
    assert f"{label}（rollback #{rollback_log[1]}）" in recorded_lines[1]


# --- real process smoke ---------------------------------------------------------------


@when(parsers.parse('the installed "{command}" executable records a decision'))
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


@then("it exits with status 0 and the line is in the Change state")
def smoke_result(home: Path, last_call: LastCall) -> None:
    assert last_call.outcome is not None and last_call.outcome.code == 0, last_call.outcome
    assert last_call.outcome.data["line"] in change_state(home).read_text().splitlines()
