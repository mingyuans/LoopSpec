"""Steps for `loopspec plan validate/create/show/list/approve/archive`."""

from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path

import pytest
from pytest_bdd import given, parsers, then, when

from tests.conftest import CliOutcome, LastCall
from tests.steps.common import outcome_of
from tests.workflow_helpers import (
    BUGFIX_FLOW,
    CHANGE,
    DOCS_FLOW,
    approve,
    create_draft,
    new_change,
    snapshot,
    status,
    write_request,
)

RunCli = Callable[..., CliOutcome]

FLOWS = {"docs": DOCS_FLOW, "bugfix": BUGFIX_FLOW}


@pytest.fixture
def request_file() -> dict[str, str]:
    """The request written by a setup step, relative to the workflow home."""
    return {}


@pytest.fixture
def draft_digests() -> list[str]:
    """Digests returned by each successful `plan create` of the scenario, in order."""
    return []


# --- setup ----------------------------------------------------------------------------


@given("隔离项目中有一个新建的 Change")
def fresh_change(home: Path) -> None:
    new_change(home)
    assert status(home)["status"] == "unplanned"


@given(parsers.re(r'^已写好 "(?P<flow>[^"]+)" 流程的 Plan 请求$'))
def request_written(
    home: Path,
    request_file: dict[str, str],
    home_snapshot: dict[str, bytes],
    flow: str,
) -> None:
    request_file["path"] = write_request(home, FLOWS[flow])
    home_snapshot.update(snapshot(home))


@given(parsers.re(r'^已用 "(?P<flow>[^"]+)" 流程新建 Plan 草稿$'))
def draft_created(home: Path, draft_digests: list[str], flow: str) -> None:
    result = create_draft(home, FLOWS[flow])
    assert result["status"] == "draft", result
    draft_digests.append(result["digest"])


@given(parsers.re(r'^草稿 "(?P<plan>[^"]+)" 已按展示的摘要批准$'))
def draft_approved(home: Path, plan: str) -> None:
    result = approve(home, plan)
    assert result["status"] == "approved", result


# --- actions --------------------------------------------------------------------------


@when("校验该请求")
def validate_request(run_cli: RunCli, last_call: LastCall, request_file: dict[str, str]) -> None:
    last_call.outcome = run_cli("plan", "validate", "-c", CHANGE, "-f", request_file["path"])


@when(parsers.re(r'^用 "(?P<flow>[^"]+)" 流程新建 Plan$'))
def create_plan(
    home: Path, run_cli: RunCli, last_call: LastCall, draft_digests: list[str], flow: str
) -> None:
    request = write_request(home, FLOWS[flow])
    last_call.outcome = run_cli("plan", "create", "-c", CHANGE, "-f", request)
    if last_call.outcome.code == 0:
        draft_digests.append(last_call.outcome.data["digest"])


@when(parsers.re(r'^用错误的摘要批准 Plan "(?P<plan>[^"]+)"$'))
def approve_wrong_digest(run_cli: RunCli, last_call: LastCall, plan: str) -> None:
    last_call.outcome = run_cli("plan", "approve", "-c", CHANGE, "-p", plan, "--digest", "0" * 64)


@when(parsers.re(r'^归档 Plan "(?P<plan>[^"]+)"$'))
def archive_plan(run_cli: RunCli, last_call: LastCall, plan: str) -> None:
    last_call.outcome = run_cli("plan", "archive", "-c", CHANGE, "-p", plan)


@when("列出 Change 的全部 Plan")
def list_plans(run_cli: RunCli, last_call: LastCall) -> None:
    last_call.outcome = run_cli("plan", "list", "-c", CHANGE)


# --- outcomes -------------------------------------------------------------------------


@then("返回的摘要是 64 位十六进制")
def digest_is_sha256(last_call: LastCall) -> None:
    data = outcome_of(last_call).data
    assert re.fullmatch(r"[0-9a-f]{64}", data["digest"]), data


@then("新草稿的摘要与上一次不同")
def digest_changed(draft_digests: list[str]) -> None:
    assert len(draft_digests) >= 2 and draft_digests[-1] != draft_digests[-2], draft_digests


@then("plan show 展示的是最新草稿的摘要")
def show_has_latest_digest(run_cli: RunCli, draft_digests: list[str]) -> None:
    shown = run_cli("plan", "show", "-c", CHANGE)
    assert shown.code == 0, shown.data
    assert shown.data["meta"]["digest"] == draft_digests[-1]


@then(parsers.re(r'^Change 状态为 "(?P<expected>[^"]+)"$'))
def change_status_is(home: Path, expected: str) -> None:
    assert status(home)["status"] == expected


@then(parsers.re(r'^Plan 列表依次为 "(?P<expected>[^"]+)"$'))
def plan_listing(last_call: LastCall, expected: str) -> None:
    data = outcome_of(last_call).data
    listing = [f"{item['plan']}:{item['status']}" for item in data["plans"]]
    assert listing == expected.split(","), data
