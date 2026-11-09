"""Steps for revising an approved Plan (`plan validate/approve -f`), `plan rollback`
and `change history`."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
from pytest_bdd import given, parsers, then, when

from tests.conftest import QA_FLOW_ONE_RETRY, CliOutcome, LastCall
from tests.steps.common import outcome_of
from tests.workflow_helpers import (
    CHANGE,
    DOCS_FLOW,
    create_approved,
    fail_gate,
    node_status,
    pass_node,
    run_until,
    snapshot,
    status,
    write_request,
)

RunCli = Callable[..., CliOutcome]


@pytest.fixture
def revision() -> dict:
    """The revision request of the scenario: its path and the digest its preview returned."""
    return {}


def instance_flow(instance: str) -> list[dict]:
    return [*DOCS_FLOW, {"id": instance, "use": "requirements", "requires": ["requirements"]}]


def preview(
    run_cli: RunCli,
    home: Path,
    revision: dict,
    base: int,
    instance: str,
    before: dict[str, bytes] | None = None,
) -> CliOutcome:
    """Write the revision request, then preview it; `before` captures the home in between."""
    request = write_request(home, instance_flow(instance), name="revision.yaml", base_revision=base)
    if before is not None:
        before.update(snapshot(home))
    outcome = run_cli("plan", "validate", "-c", CHANGE, "-f", request)
    revision["request"] = request
    revision["digest"] = outcome.data.get("digest")
    return outcome


# --- setup ----------------------------------------------------------------------------


@given("已批准的文档流程 Plan 中 requirements 节点已完成")
def docs_plan_with_requirements_done(home: Path) -> None:
    create_approved(home, DOCS_FLOW)
    pass_node(home, "requirements/proposal")
    assert node_status(home, "requirements/proposal") == "done"


@given("隔离项目中有一个最多返工一次的 QA Plan")
def approved_qa_plan(home: Path) -> None:
    create_approved(home, QA_FLOW_ONE_RETRY)


@given(parsers.parse('后端代码已修改且 "{gate}" Gate 判定失败'))
def backend_changed_and_gate_failed(home: Path, tmp_path: Path, gate: str) -> None:
    (tmp_path / "backend/code.py").write_text("changed\n")
    run_until(home, gate)
    fail_gate(home, gate)
    assert node_status(home, gate) == "failed"


@given(parsers.parse('"{gate}" Gate 判定失败并已回滚一次'))
def gate_failed_and_rolled_back(run_cli: RunCli, home: Path, gate: str) -> None:
    run_until(home, gate)
    fail_gate(home, gate)
    outcome = run_cli("plan", "rollback", "-c", CHANGE, "-p", "001")
    assert outcome.code == 0, outcome.data


@given(parsers.parse('requirements 节点重做后 "{gate}" Gate 再次判定失败'))
def gate_fails_again(home: Path, gate: str) -> None:
    run_until(home, gate)
    fail_gate(home, gate)


@given(parsers.re(r'已以基准修订号 "(?P<base>\d+)" 预览新增 "(?P<instance>[^"]+)" 实例的修订'))
def previewed_revision(
    run_cli: RunCli, home: Path, revision: dict, base: str, instance: str
) -> None:
    outcome = preview(run_cli, home, revision, int(base), instance)
    assert outcome.code == 0, outcome.data


# --- actions --------------------------------------------------------------------------


@when(parsers.re(r'以基准修订号 "(?P<base>\d+)" 预览新增 "(?P<instance>[^"]+)" 实例的修订'))
def preview_revision(
    run_cli: RunCli,
    home: Path,
    last_call: LastCall,
    revision: dict,
    home_snapshot: dict[str, bytes],
    base: str,
    instance: str,
) -> None:
    last_call.outcome = preview(run_cli, home, revision, int(base), instance, home_snapshot)


@when("凭预览摘要确认该修订")
def approve_revision(run_cli: RunCli, last_call: LastCall, revision: dict) -> None:
    last_call.outcome = run_cli(
        "plan", "approve", "-c", CHANGE, "-p", "001",
        "-f", revision["request"], "--digest", revision["digest"],
    )  # fmt: skip


@when(parsers.parse('回滚 Plan "{plan}"'))
def rollback(run_cli: RunCli, last_call: LastCall, plan: str) -> None:
    last_call.outcome = run_cli("plan", "rollback", "-c", CHANGE, "-p", plan)


@when("查看 Change 历史")
def history(run_cli: RunCli, last_call: LastCall) -> None:
    last_call.outcome = run_cli("change", "history", CHANGE)


# --- outcomes -------------------------------------------------------------------------


@then(parsers.parse('新增实例列表为 "{instance}"'))
def added_instances(last_call: LastCall, instance: str) -> None:
    data = outcome_of(last_call).data
    assert data["addedInstances"] == [instance], data
    assert data["rerunNodes"] == [], data


@then(parsers.parse('Plan 当前修订号为 "{revision_number}"'))
def plan_revision_is(home: Path, revision_number: str) -> None:
    assert status(home)["revision"] == int(revision_number)


@then(parsers.parse('重置范围包含 "{node}"'))
def reset_contains(last_call: LastCall, node: str) -> None:
    data = outcome_of(last_call).data
    assert node in data["reset"], data


@then(parsers.parse('历史中只有一条针对 "{gate}" 的 "{kind}" 记录'))
def single_history_record(last_call: LastCall, gate: str, kind: str) -> None:
    data = outcome_of(last_call).data
    assert data["plan"] == "001", data
    [record] = data["attempts"]
    assert record["kind"] == kind and record["gate"] == gate, record
