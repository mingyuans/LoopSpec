"""Steps for `loopspec registry update/apply` against a local `file://` registry."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from urllib.parse import quote

import pytest
from pytest_bdd import given, parsers, then, when

from tests.conftest import CliOutcome, LastCall
from tests.registry_helpers import commit, make_registry
from tests.steps.common import outcome_of

RunCli = Callable[..., CliOutcome]
LOCAL_EDIT = "mine\n"


@pytest.fixture
def registry_plan() -> dict[str, str]:
    """The planId (and upstream commit) returned by the scenario's `registry update`."""
    return {}


# --- given ----------------------------------------------------------------------------


@given(parsers.parse('工作流 home 配置了打过 "{tag}" 标签的本地注册表'))
def configured_registry(home: Path, tmp_path: Path, tag: str) -> None:
    registry = make_registry(tmp_path / "upstream-registry")
    commit(registry, "release", tag=tag)
    # pytest-bdd names tmp_path after the Chinese scenario title, and registry.url only
    # accepts an ASCII path, so the file:// URL is percent-encoded (git decodes it).
    registry_url = "file://" + quote(str(registry.resolve()))
    (home / "config.yaml").write_text(f"workflow: {{}}\nregistry:\n  url: {registry_url}\n")


@given(parsers.parse('本地修改了 "{relative}"'))
def locally_modified(home: Path, relative: str) -> None:
    path = home / relative
    assert path.is_file(), path
    path.write_text(LOCAL_EDIT)


@given("已生成一份注册表同步计划")
def plan_generated(run_cli: RunCli, registry_plan: dict[str, str]) -> None:
    outcome = run_cli("registry", "update")
    assert outcome.code == 0, outcome.data
    registry_plan["planId"] = outcome.data["planId"]


@given("该同步计划已被应用")
def plan_applied(run_cli: RunCli, registry_plan: dict[str, str]) -> None:
    outcome = run_cli("registry", "apply", "--plan", registry_plan["planId"])
    assert outcome.code == 0 and outcome.data["applied"] is True, outcome.data


# --- when -----------------------------------------------------------------------------


@when("用户检查注册表更新")
def check_update(run_cli: RunCli, last_call: LastCall) -> None:
    last_call.outcome = run_cli("registry", "update")


@when("用户应用该同步计划")
def apply_plan(run_cli: RunCli, last_call: LastCall, registry_plan: dict[str, str]) -> None:
    last_call.outcome = run_cli("registry", "apply", "--plan", registry_plan["planId"])


@when(parsers.parse('用户应用该同步计划并裁决 "{relative}" 保留本地'))
def apply_keeping_local(
    run_cli: RunCli, last_call: LastCall, registry_plan: dict[str, str], relative: str
) -> None:
    last_call.outcome = run_cli(
        "registry", "apply", "--plan", registry_plan["planId"], "--resolve", f"{relative}=local"
    )


# --- then -----------------------------------------------------------------------------


@then("返回了同步计划编号")
def plan_id_returned(last_call: LastCall) -> None:
    data = outcome_of(last_call).data
    plan_id = data.get("planId")
    assert isinstance(plan_id, str) and plan_id, data


@then(parsers.parse('工作流 home 中没有 "{name}"'))
def file_absent(home: Path, name: str) -> None:
    assert not (home / name).exists()


@then(parsers.parse('"{relative}" 仍是本地修改的内容'))
def local_content_kept(home: Path, last_call: LastCall, relative: str) -> None:
    assert outcome_of(last_call).data["kept"] == [relative]
    assert (home / relative).read_text() == LOCAL_EDIT


@then(parsers.re(r'Fragment "(?P<name>[^"]+)" 的注册表来源版本为 "(?P<tag>[^"]+)"'))
def fragment_synced_tag(last_call: LastCall, name: str, tag: str) -> None:
    fragments = {item["name"]: item for item in outcome_of(last_call).data["fragments"]}
    assert fragments[name]["registry"]["syncedTag"] == tag, fragments[name]
