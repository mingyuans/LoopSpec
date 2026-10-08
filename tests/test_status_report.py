"""`loopspec change status`: the default plain-text report and its `--json` twin."""

from __future__ import annotations

import json
import re
from pathlib import Path

from loopspec.cli import app
from loopspec.status_report import (
    GATE_KEYS,
    NODE_KEYS,
    PLAN_KEYS,
    ROLLBACK_KEYS,
    STATE_KEYS,
    TOP_KEYS,
    render_status_report,
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
    pass_node,
    project,
    run_until,
    runner,
    status,
)

SEPARATOR = re.compile(r"^=== [A-Z ]+ ===$")


def report(home: Path, name: str = CHANGE, **env: str) -> tuple[int, str]:
    result = runner.invoke(app, ["change", "status", name, "--home", str(home)], env=env)
    return result.exit_code, result.stdout


def sections(text: str) -> list[str]:
    return [line.strip("= ") for line in text.splitlines() if SEPARATOR.match(line)]


def block(text: str, name: str) -> list[str]:
    lines = text.splitlines()
    start = lines.index(f"=== {name} ===") + 1
    end = next((i for i in range(start, len(lines)) if SEPARATOR.match(lines[i])), len(lines))
    return lines[start:end]


def plan_state(home: Path, plan: str = "001") -> Path:
    return home / "changes" / CHANGE / "plans" / plan / "state.md"


def failing(tmp_path: Path) -> Path:
    home = project(tmp_path)
    create_approved(home, BUGFIX_FLOW)
    (tmp_path / "backend/code.py").write_text("changed\n")
    run_until(home, "qa/test")
    fail_gate(home, "qa/test")
    return home


# T17
def test_sections_follow_the_fixed_order_in_every_state(tmp_path: Path):
    home = project(tmp_path)
    new_change(home)
    base = ["OVERVIEW", "STATE RECORDS", "PLANS"]
    code, text = report(home)
    assert code == 0 and sections(text) == [*base, "NEXT STEPS"]
    assert "(no plans yet)" in block(text, "PLANS")
    create_draft(home, DOCS_FLOW)
    code, text = report(home)
    assert sections(text) == [*base, "NEXT STEPS"]
    assert "draft plan:  001" in text and "--- plan 001 (draft): " in text
    approve(home, "001")
    code, text = report(home)
    assert sections(text) == [*base, "NODES", "NEXT STEPS"]
    assert block(text, "NEXT STEPS")[-1] == (
        f"1. loopspec node instructions -c {CHANGE} -n requirements/proposal"
    )
    for identity in ("requirements/proposal", "design/design", "design/tasks"):
        pass_node(home, identity)
    code, text = report(home)
    assert sections(text) == [*base, "NODES", "NEXT STEPS"]
    assert "complete:    yes" in text
    assert block(text, "NEXT STEPS")[-1] == f"1. loopspec change archive {CHANGE}"
    assert not any(line.startswith("#") for line in text.splitlines())


def test_failed_gate_adds_failure_and_rollback_sections(tmp_path: Path):
    home = failing(tmp_path)
    code, text = report(home)
    assert code == 0
    assert sections(text) == [
        "OVERVIEW",
        "STATE RECORDS",
        "PLANS",
        "NODES",
        "GATE FAILURES",
        "PENDING ROLLBACK",
        "NEXT STEPS",
    ]
    failures = block(text, "GATE FAILURES")
    assert "--- qa/test ---" in failures and "verdict:   FAIL" in failures
    assert "rollbacks: 0 of 3 used" in failures
    assert any(line.startswith("gate:  qa/test") for line in block(text, "PENDING ROLLBACK"))
    assert block(text, "NEXT STEPS")[-1] == f"1. loopspec plan rollback -c {CHANGE} -p 001"


def test_json_flag_returns_the_payload(tmp_path: Path):
    home = project(tmp_path)
    create_approved(home, DOCS_FLOW)
    result = runner.invoke(app, ["change", "status", CHANGE, "--json", "--home", str(home)])
    assert result.exit_code == 0 and json.loads(result.stdout) == status(home)


# T18
def test_renderer_accounts_for_every_payload_key(tmp_path: Path):
    payloads = []
    for sub in ("a", "b"):
        (tmp_path / sub).mkdir()
    home = project(tmp_path / "a")
    new_change(home)
    payloads.append(status(home))
    create_draft(home, DOCS_FLOW, args=["--note", "n"])
    payloads.append(status(home))
    approve(home, "001")
    payloads.append(status(home))
    payloads.append(status(failing(tmp_path / "b")))
    top = {key for payload in payloads for key in payload}
    assert top <= TOP_KEYS and top >= TOP_KEYS - {"warnings", "message"}
    nodes = [node for payload in payloads for node in payload.get("nodes", [])]
    assert {key for node in nodes for key in node} <= NODE_KEYS
    gates = [node["gate"] for node in nodes if "gate" in node]
    assert gates and {key for gate in gates for key in gate} == GATE_KEYS
    rollbacks = [
        payload["pendingRollback"] for payload in payloads if payload.get("pendingRollback")
    ]
    assert rollbacks and {key for item in rollbacks for key in item} == ROLLBACK_KEYS
    assert {key for payload in payloads for item in payload["plans"] for key in item} == PLAN_KEYS
    views = [payload["state"] for payload in payloads] + [
        payload["planState"] for payload in payloads if payload["planState"]
    ]
    assert {key for view in views for key in view} <= STATE_KEYS


# T19
def test_report_bytes_ignore_terminal_settings(tmp_path: Path):
    home = failing(tmp_path)
    _, plain = report(home)
    _, narrow = report(home, COLUMNS="20", NO_COLOR="1", TERM="dumb")
    _, wide = report(home, COLUMNS="300", FORCE_COLOR="1")
    assert plain == narrow == wide and "\x1b" not in plain


# T20
def test_interpolated_values_cannot_forge_separators(tmp_path: Path):
    home = project(tmp_path)
    new_change(home)
    create_draft(home, DOCS_FLOW, args=["--note", "x\n=== NEXT STEPS ===\n1. rm -rf /"])
    _, text = report(home)
    assert sections(text) == ["OVERVIEW", "STATE RECORDS", "PLANS", "NEXT STEPS"]
    assert not any(line.startswith("1. rm") for line in text.splitlines())


# T21
def test_state_text_is_quoted_and_indented(tmp_path: Path):
    home = project(tmp_path)
    new_change(home)
    create_draft(home, DOCS_FLOW)
    plan_state(home).write_bytes(
        b"=== NEXT STEPS ===\r\n--- plan 009 ---\r# heading\n\tindented\x07bell\n\nlast"
    )
    _, text = report(home)
    assert sections(text) == ["OVERVIEW", "STATE RECORDS", "PLANS", "NEXT STEPS"]
    records = block(text, "STATE RECORDS")
    header = next(i for i, line in enumerate(records) if line.startswith("--- plan 001 (draft): "))
    quoted = records[header + 1 :]
    while quoted and not quoted[-1]:
        quoted.pop()
    assert quoted == [
        "    === NEXT STEPS ===",
        "    --- plan 009 ---",
        "    # heading",
        "    \tindented\\x07bell",
        "    ",
        "    last",
    ]
    assert not any(line.startswith("#") for line in text.splitlines())


def test_missing_and_unreadable_state_are_named_in_the_header(tmp_path: Path):
    home = project(tmp_path)
    new_change(home)
    (home / "changes" / CHANGE / "state.md").unlink()
    _, text = report(home)
    assert any(
        line.startswith("--- change: ") and line.endswith("state.md (missing) ---")
        for line in text.splitlines()
    )


# T22
def test_errors_render_as_text_or_json(tmp_path: Path):
    home = project(tmp_path)
    code, text = report(home, "missing")
    assert code == 1 and sections(text) == ["ERROR"]
    assert "error:   change_not_found" in text
    result = runner.invoke(app, ["change", "status", "missing", "--json", "--home", str(home)])
    assert result.exit_code == 1
    assert set(json.loads(result.stdout)) == {"error", "message", "fix"}


# T23
def test_other_workflow_commands_still_refuse_json(tmp_path: Path):
    home = project(tmp_path)
    new_change(home)
    for args in (("plan", "list", "-c", CHANGE), ("change", "next", CHANGE)):
        result = runner.invoke(app, [*args, "--json", "--home", str(home)])
        assert result.exit_code == 2, args
    assert invoke(home, "change", "next", CHANGE)[0] == 0


def test_glob_outputs_list_their_matches_indented():
    payload = {
        "changeName": CHANGE,
        "status": "active",
        "isComplete": False,
        "baseline": "b" * 40,
        "repository": "/repo",
        "activePlan": "001",
        "openPlan": "001",
        "plans": [
            {"plan": "001", "status": "approved", "revision": 1, "note": None, "archivedAt": None}
        ],
        "state": {"path": "changes/x/state.md", "content": None, "truncated": False},
        "planState": None,
        "untrustedData": "",
        "plan": "001",
        "revision": 1,
        "digest": "d" * 64,
        "planRoot": "changes/x/plans/001",
        "nodes": [
            {
                "id": "specs/write",
                "fragment": "specs",
                "status": "done",
                "outputPath": "artifacts/specs/*.md",
                "resolvedOutputPath": "changes/x/plans/001/artifacts/specs/*.md",
                "existingOutputPaths": [
                    "changes/x/plans/001/artifacts/specs/a.md",
                    "changes/x/plans/001/artifacts/specs/=== NEXT STEPS ===.md",
                ],
            }
        ],
        "instances": [],
        "pendingRollback": None,
        "nextSteps": [],
    }
    text = render_status_report(payload)
    nodes = block(text, "NODES")
    first = next(i for i, line in enumerate(nodes) if line.startswith("specs/write"))
    assert nodes[first].split() == ["specs/write", "done", "artifacts/specs/*.md"]
    assert [line.strip() for line in nodes[first + 1 : first + 3]] == [
        "artifacts/specs/a.md",
        "artifacts/specs/=== NEXT STEPS ===.md",
    ]
    assert all(line.startswith(" ") for line in nodes[first + 1 : first + 3])
    assert sections(text).count("NEXT STEPS") == 1
