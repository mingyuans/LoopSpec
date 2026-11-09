"""Steps for `loopspec hook pre-tool-use`, fed real Plans created through the CLI."""

from __future__ import annotations

import json
import shlex
from collections.abc import Callable
from pathlib import Path
from typing import Any

from pytest_bdd import given, parsers, then, when

from tests.conftest import CliOutcome, LastCall
from tests.steps.common import outcome_of
from tests.workflow_helpers import (
    CHANGE,
    DOCS_FLOW,
    create_draft,
    loaded,
    new_change,
)

RunApp = Callable[..., CliOutcome]


def approved_plan_file(home: Path) -> Path:
    return loaded(home).root / "plan.yaml"


def draft_plan_file(home: Path) -> Path:
    return home / "changes" / CHANGE / "plans" / "001" / "plan.yaml"


def payload(tool: str, cwd: Path, **tool_input: Any) -> dict[str, Any]:
    return {
        "hook_event_name": "PreToolUse",
        "tool_name": tool,
        "tool_input": tool_input,
        "cwd": str(cwd),
    }


def send(run_app: RunApp, last_call: LastCall, stdin: str) -> None:
    last_call.outcome = run_app("hook", "pre-tool-use", input=stdin)


# --- setup ----------------------------------------------------------------------------


@given("隔离项目中有一个草稿状态的文档流程 Plan")
def draft_plan(home: Path) -> None:
    new_change(home)
    create_draft(home, DOCS_FLOW)
    assert "status: draft" in draft_plan_file(home).read_text()


# --- actions --------------------------------------------------------------------------


@when(parsers.re(r'AI 工具用 "(?P<tool>[^"]+)" 写入已批准 Plan 的 plan\.yaml'))
def write_approved(run_app, last_call: LastCall, home: Path, tmp_path: Path, tool: str) -> None:
    target = str(approved_plan_file(home))
    send(run_app, last_call, json.dumps(payload(tool, tmp_path, file_path=target, content="x")))


@when(parsers.re(r'AI 工具用 "(?P<tool>[^"]+)" 读取已批准 Plan 的 plan\.yaml'))
def read_approved(run_app, last_call: LastCall, home: Path, tmp_path: Path, tool: str) -> None:
    target = str(approved_plan_file(home))
    send(run_app, last_call, json.dumps(payload(tool, tmp_path, file_path=target)))


@when(parsers.re(r'AI 工具用 "(?P<tool>[^"]+)" 写入 "(?P<path>[^"]+)"'))
def write_other(run_app, last_call: LastCall, tmp_path: Path, tool: str, path: str) -> None:
    send(run_app, last_call, json.dumps(payload(tool, tmp_path, file_path=path, content="x")))


@when("Hook 收到非 JSON 的输入")
def non_json(run_app: RunApp, last_call: LastCall) -> None:
    send(run_app, last_call, "not json")


@when(parsers.re(r'AI 工具用 "(?P<tool>[^"]+)" 编辑已批准 Plan 的 plan\.yaml'))
def edit_approved(run_app, last_call: LastCall, home: Path, tmp_path: Path, tool: str) -> None:
    edit = {"old_string": "status: approved", "new_string": "status: approved "}
    target = str(approved_plan_file(home))
    send(run_app, last_call, json.dumps(payload(tool, tmp_path, file_path=target, **edit)))


@when(parsers.re(r'AI 工具用 "(?P<tool>[^"]+)" 编辑草稿 Plan 的 plan\.yaml'))
def edit_draft(run_app, last_call: LastCall, home: Path, tmp_path: Path, tool: str) -> None:
    edit = {"old_string": "status: draft", "new_string": "status: draft "}
    target = str(draft_plan_file(home))
    send(run_app, last_call, json.dumps(payload(tool, tmp_path, file_path=target, **edit)))


@when(parsers.re(r'AI 工具执行 Bash 命令 "(?P<command>[^"]+)" 作用于已批准 Plan 的 plan\.yaml'))
def bash_on_approved(
    run_app, last_call: LastCall, home: Path, tmp_path: Path, command: str
) -> None:
    full = f"{command} {shlex.quote(str(approved_plan_file(home)))}"
    send(run_app, last_call, json.dumps(payload("Bash", tmp_path, command=full)))


@when(
    parsers.re(
        r'AI 工具用 "(?P<tool>[^"]+)" 新建 Plan "(?P<plan>[^"]+)" 的 plan\.yaml，'
        r'内容状态为 "(?P<status>[^"]+)"'
    )
)
def forge_plan(
    run_app, last_call: LastCall, home: Path, tmp_path: Path, tool: str, plan: str, status: str
) -> None:
    target = home / "changes" / CHANGE / "plans" / plan / "plan.yaml"
    assert not target.exists()
    content = f"meta:\n  plan: '{plan}'\n  status: {status}\n  revision: 1\nspec:\n  flow: []\n"
    send(
        run_app,
        last_call,
        json.dumps(payload(tool, tmp_path, file_path=str(target), content=content)),
    )


# --- outcomes -------------------------------------------------------------------------


@then(parsers.parse('Hook 拒绝该操作，理由提到 "{text}"'))
def denied(last_call: LastCall, text: str) -> None:
    outcome = outcome_of(last_call)
    assert outcome.code == 0, outcome.output
    decision = outcome.data["hookSpecificOutput"]
    assert decision["hookEventName"] == "PreToolUse"
    assert decision["permissionDecision"] == "deny"
    assert text in decision["permissionDecisionReason"], decision


@then("Hook 静默放行")
def allowed_silently(last_call: LastCall) -> None:
    outcome = outcome_of(last_call)
    assert outcome.code == 0 and outcome.output == "", outcome.output
