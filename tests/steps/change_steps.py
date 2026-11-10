"""Steps for `loopspec change new/status/next/history/artifacts/archive`."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from pathlib import Path

import pytest
from pytest_bdd import given, parsers, then, when

from tests.conftest import CliOutcome, LastCall
from tests.steps.common import outcome_of
from tests.workflow_helpers import DOCS_FLOW, create_approved, new_change, pass_node, write_request

RunCli = Callable[..., CliOutcome]

DOCS_NODES = ("requirements/proposal", "design/design", "design/tasks")


@pytest.fixture
def status_reports() -> list[dict]:
    """Every `change status` payload of the scenario, in order."""
    return []


@pytest.fixture
def archive_month() -> dict[str, str]:
    """The `archive/YYYY-MM` directory expected, captured just before `change archive` runs."""
    return {}


def active_dir(home: Path, name: str) -> Path:
    return home / "changes" / name


# --- setup ----------------------------------------------------------------------------


@given(parsers.re(r'已新建 Change "(?P<name>[^"]+)"'))
def change_created(home: Path, name: str) -> None:
    new_change(home, name)
    assert (active_dir(home, name) / ".workflow.yaml").is_file()


@given(parsers.re(r'Change "(?P<name>[^"]+)" 的文档流程已全部完成'))
def completed_docs_plan(home: Path, run_cli: RunCli, name: str) -> None:
    create_approved(home, DOCS_FLOW, name)
    for identity in DOCS_NODES:
        pass_node(home, identity, name)
    outcome = run_cli("change", "status", name)
    assert outcome.code == 0 and outcome.data["status"] == "complete", outcome.data


# --- actions --------------------------------------------------------------------------


@when(parsers.re(r'新建 Change "(?P<name>[^"]+)"'))
def change_new(run_cli: RunCli, last_call: LastCall, name: str) -> None:
    last_call.outcome = run_cli("change", "new", name)


@when(parsers.re(r'查询 Change "(?P<name>[^"]+)" 的状态'))
def change_status(
    run_cli: RunCli, last_call: LastCall, status_reports: list[dict], name: str
) -> None:
    last_call.outcome = run_cli("change", "status", name)
    if last_call.outcome.code == 0:
        status_reports.append(last_call.outcome.data)


@when(parsers.re(r'查询 Change "(?P<name>[^"]+)" 的下一步'))
def change_next(run_cli: RunCli, last_call: LastCall, name: str) -> None:
    last_call.outcome = run_cli("change", "next", name)


@when(parsers.re(r'查询 Change "(?P<name>[^"]+)" 的历史'))
def change_history(run_cli: RunCli, last_call: LastCall, name: str) -> None:
    last_call.outcome = run_cli("change", "history", name)


@when(parsers.re(r'查询 Change "(?P<name>[^"]+)" 的产物'))
def change_artifacts(run_cli: RunCli, last_call: LastCall, name: str) -> None:
    last_call.outcome = run_cli("change", "artifacts", name)


@when(parsers.re(r'用文档流程为 Change "(?P<name>[^"]+)" 创建 Plan 草稿'))
def docs_draft(home: Path, run_cli: RunCli, last_call: LastCall, name: str) -> None:
    request = write_request(home, DOCS_FLOW, change=name)
    last_call.outcome = run_cli("plan", "create", "-c", name, "-f", request)


@when(parsers.re(r'依次完成 Change "(?P<name>[^"]+)" 文档流程的全部节点'))
def pass_docs_nodes(home: Path, run_cli: RunCli, last_call: LastCall, name: str) -> None:
    for identity in DOCS_NODES:
        pass_node(home, identity, name)
    last_call.outcome = run_cli("change", "next", name)


@when(parsers.re(r'归档 Change "(?P<name>[^"]+)"'))
def archive_change(
    run_cli: RunCli, last_call: LastCall, archive_month: dict[str, str], name: str
) -> None:
    archive_month["path"] = f"archive/{date.today().strftime('%Y-%m')}"
    last_call.outcome = run_cli("change", "archive", name)


@when(parsers.re(r'强制归档 Change "(?P<name>[^"]+)"'))
def force_archive_change(run_cli: RunCli, last_call: LastCall, name: str) -> None:
    last_call.outcome = run_cli("change", "archive", name, "--force")


@when(parsers.re(r'以 Change 名 "(?P<name>[^"]+)" 加 --all 归档'))
def archive_name_and_all(run_cli: RunCli, last_call: LastCall, name: str) -> None:
    last_call.outcome = run_cli("change", "archive", name, "--all")


# --- outcomes -------------------------------------------------------------------------


@then("工作流目录下没有出现任何 Change 目录")
def no_change_directory(home: Path, tmp_path: Path) -> None:
    changes = home / "changes"
    assert not changes.exists() or not any(changes.iterdir())
    assert not (home / "x").exists() and not (tmp_path / "x").exists()


@then(parsers.re(r'状态报告的下一步是 "(?P<step>[^"]+)"'))
def report_next_step(status_reports: list[dict], step: str) -> None:
    assert status_reports[-1]["nextSteps"] == [step], status_reports[-1]


@then("change next 的下一步与最近一次状态报告一致")
def next_matches_status(last_call: LastCall, status_reports: list[dict]) -> None:
    data = outcome_of(last_call).data
    assert data["nextSteps"] == status_reports[-1]["nextSteps"]
    assert data["status"] == status_reports[-1]["status"]


@then(parsers.re(r'Change "(?P<name>[^"]+)" 仍在活动目录中'))
def still_active(home: Path, name: str) -> None:
    assert (active_dir(home, name) / ".workflow.yaml").is_file()


@then(parsers.re(r'Change "(?P<name>[^"]+)" 已不在活动目录中'))
def no_longer_active(home: Path, name: str) -> None:
    assert not active_dir(home, name).exists()


@then(parsers.re(r'Change "(?P<name>[^"]+)" 已移动到当月归档目录'))
def moved_to_archive(
    home: Path, last_call: LastCall, archive_month: dict[str, str], name: str
) -> None:
    target = home / archive_month["path"] / name
    assert Path(outcome_of(last_call).data["destination"]) == target.resolve()
    assert (target / ".workflow.yaml").is_file()
    assert not active_dir(home, name).exists()


@then("产物位置是当月归档目录")
def artifacts_in_archive(last_call: LastCall, archive_month: dict[str, str]) -> None:
    data = outcome_of(last_call).data
    locations = [item["location"] for item in data["locations"]]
    assert locations == [archive_month["path"]], data
