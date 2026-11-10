"""Steps for `loopspec node instructions`, `gate begin` and `gate record`."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
from pytest_bdd import given, parsers, then, when

from tests.conftest import CliOutcome, LastCall
from tests.steps.common import outcome_of
from tests.workflow_helpers import (
    BUGFIX_FLOW,
    CHANGE,
    create_draft,
    loaded,
    new_change,
    node_status,
    run_until,
    status,
)

RunCli = Callable[..., CliOutcome]


@pytest.fixture
def gate_round() -> dict[str, str]:
    """The round id returned by the scenario's `gate begin`."""
    return {}


# --- setup ----------------------------------------------------------------------------


@given("隔离项目中只有一个草稿状态的缺陷修复 Plan")
def draft_bugfix_plan(home: Path) -> None:
    new_change(home)
    draft = create_draft(home, BUGFIX_FLOW)
    assert draft["plan"] == "001", draft


@given(parsers.parse('后端代码已修改且流程推进到 "{node}"'))
def backend_changed_until(home: Path, tmp_path: Path, node: str) -> None:
    (tmp_path / "backend/code.py").write_text("changed\n")
    run_until(home, node)
    assert node_status(home, node) == "ready"


# --- actions --------------------------------------------------------------------------


@when(parsers.parse('获取节点 "{node}" 的执行指令'))
def node_instructions(run_cli: RunCli, last_call: LastCall, node: str) -> None:
    last_call.outcome = run_cli("node", "instructions", "-c", CHANGE, "-n", node)


@when(parsers.parse('开始 Gate "{gate}" 的审查轮次'))
def gate_begin(run_cli: RunCli, last_call: LastCall, gate_round: dict[str, str], gate: str) -> None:
    last_call.outcome = run_cli("gate", "begin", "-c", CHANGE, "-n", gate)
    if "roundId" in last_call.outcome.data:
        gate_round["roundId"] = last_call.outcome.data["roundId"]


@when(parsers.re(r'不带轮次与报告记录 Gate "(?P<gate>[^"]+)"'))
def gate_record_bare(run_cli: RunCli, last_call: LastCall, gate: str) -> None:
    last_call.outcome = run_cli("gate", "record", "-c", CHANGE, "-n", gate)


@when(parsers.re(r'带报告记录 Gate "(?P<gate>[^"]+)"'))
def gate_record_with_report(run_cli: RunCli, last_call: LastCall, gate: str) -> None:
    last_call.outcome = run_cli(
        "gate", "record", "-c", CHANGE, "-n", gate, "--report", "artifacts/reports/x.yaml"
    )


@when(
    parsers.re(
        r'写入结论为 "(?P<verdict>[^"]+)" 的报告 "(?P<report>[^"]+)" '
        r'并以该轮次记录 Gate "(?P<gate>[^"]+)"'
    )
)
def gate_record_with_round(
    run_cli: RunCli,
    last_call: LastCall,
    home: Path,
    gate_round: dict[str, str],
    verdict: str,
    report: str,
    gate: str,
) -> None:
    path = loaded(home).root / report
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"verdict: {verdict}\nsummary: 后端测试已实际运行\n")
    last_call.outcome = run_cli(
        "gate", "record", "-c", CHANGE, "-n", gate,
        "--round", gate_round["roundId"], "--report", report,
    )  # fmt: skip


# --- outcomes -------------------------------------------------------------------------


@then("返回非空的执行指令")
def has_instruction(last_call: LastCall) -> None:
    data = outcome_of(last_call).data
    assert isinstance(data.get("instruction"), str) and data["instruction"].strip(), data


@then(parsers.parse('解析后的产物路径为活动 Plan 目录下的 "{relative}"'))
def resolved_output_path(home: Path, last_call: LastCall, relative: str) -> None:
    data = outcome_of(last_call).data
    assert data["outputPath"] == relative, data
    assert Path(data["resolvedOutputPath"]) == loaded(home).root / relative, data


@then("返回了审查轮次编号")
def round_returned(last_call: LastCall, gate_round: dict[str, str]) -> None:
    data = outcome_of(last_call).data
    assert gate_round.get("roundId") and data["gate"] in gate_round["roundId"], data


@then("Change 已完成")
def change_complete(home: Path) -> None:
    report = status(home)
    assert report["isComplete"] is True, report["nodes"]
    assert all(node["status"] == "done" for node in report["nodes"]), report["nodes"]
