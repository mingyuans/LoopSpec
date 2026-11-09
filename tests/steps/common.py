"""Steps shared by several features; every `当` step stores its result in `last_call.outcome`."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

from pytest_bdd import given, parsers, then, when

from tests.conftest import CliOutcome, LastCall
from tests.workflow_helpers import (
    BUGFIX_FLOW,
    CHANGE,
    DOCS_FLOW,
    create_approved,
    loaded,
    node_status,
    snapshot,
    status,
)


def outcome_of(last_call: LastCall) -> CliOutcome:
    """The outcome of the scenario's most recent `当` step."""
    assert last_call.outcome is not None, "no command has run in this scenario"
    return last_call.outcome


@given("隔离项目中有一个已批准的缺陷修复 Plan")
def approved_bugfix_plan(home: Path) -> None:
    create_approved(home, BUGFIX_FLOW)
    assert status(home)["status"] == "active"


@given("隔离项目中有一个已批准的文档流程 Plan")
def approved_docs_plan(home: Path) -> None:
    create_approved(home, DOCS_FLOW)
    assert status(home)["status"] == "active"
    assert "status: approved" in (loaded(home).root / "plan.yaml").read_text()


@when(parsers.re(r'用 plan show 展示的摘要批准 Plan "(?P<plan>[^"]+)"'))
def approve_shown_digest(
    run_cli: Callable[..., CliOutcome], last_call: LastCall, plan: str
) -> None:
    shown = run_cli("plan", "show", "-c", CHANGE, "-p", plan)
    assert shown.code == 0, shown.data
    digest = shown.data["meta"]["digest"]
    last_call.outcome = run_cli("plan", "approve", "-c", CHANGE, "-p", plan, "--digest", digest)


@when("用户列出所有 Fragment")
def list_fragments(run_cli: Callable[..., CliOutcome], last_call: LastCall) -> None:
    last_call.outcome = run_cli("fragment", "list")


@then("命令成功")
def command_succeeds(last_call: LastCall) -> None:
    outcome = outcome_of(last_call)
    assert outcome.code == 0, outcome.data or outcome.output


@then(parsers.parse('命令失败，错误码为 "{error}"'))
def command_fails_with(last_call: LastCall, error: str) -> None:
    outcome = outcome_of(last_call)
    assert outcome.code == 1, outcome.data or outcome.output
    assert outcome.data.get("error") == error, outcome.data


@then(parsers.parse('输出字段 "{field}" 为 "{value}"'))
def output_field_is(last_call: LastCall, field: str, value: str) -> None:
    data = outcome_of(last_call).data
    assert field in data, data
    actual = data[field]
    rendered = json.dumps(actual) if isinstance(actual, bool) or actual is None else str(actual)
    assert rendered == value, data


@then(parsers.re(r'节点 "(?P<node>[^"]+)" 状态为 "(?P<expected>[^"]+)"'))
def node_is(home: Path, node: str, expected: str) -> None:
    assert node_status(home, node) == expected


@then("工作流目录中没有任何文件变化")
def home_unchanged(home: Path, home_snapshot: dict[str, bytes]) -> None:
    assert home_snapshot, "no snapshot was taken"
    assert snapshot(home) == home_snapshot
