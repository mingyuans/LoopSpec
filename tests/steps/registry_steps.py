"""Steps for `loopspec registry update/apply` against a local `file://` registry."""

from __future__ import annotations

import shutil
from collections.abc import Callable
from pathlib import Path
from urllib.parse import quote

import pytest
from pytest_bdd import given, parsers, then, when

from loopspec import registry_store
from tests.conftest import CliOutcome, LastCall
from tests.registry_helpers import commit, make_registry
from tests.steps.common import outcome_of
from tests.workflow_helpers import DOCS_FLOW, create_approved

RunCli = Callable[..., CliOutcome]


@pytest.fixture
def registry_plan() -> dict[str, str]:
    """The planId (and upstream commit) returned by the scenario's `registry update`."""
    return {}


@pytest.fixture
def registry_source() -> dict[str, Path]:
    """Where the scenario's registry repository lives."""
    return {}


# --- given ----------------------------------------------------------------------------


@given(parsers.parse('工作流 home 配置了打过 "{tag}" 标签的本地注册表'))
def configured_registry(
    home: Path, tmp_path: Path, tag: str, registry_source: dict[str, Path]
) -> None:
    registry = make_registry(tmp_path / "upstream-registry")
    commit(registry, "release", tag=tag)
    registry_source["path"] = registry
    # registry 模式下项目不再持有 registry 定义：去掉 home fixture 自带的内置副本。
    for kind in ("fragments", "profiles"):
        shutil.rmtree(home / kind)
    # pytest-bdd names tmp_path after the Chinese scenario title, and registry.url only
    # accepts an ASCII path, so the file:// URL is percent-encoded (git decodes it).
    registry_url = "file://" + quote(str(registry.resolve()))
    (home / "config.yaml").write_text(f"workflow: {{}}\nregistry:\n  url: {registry_url}\n")


@given("已生成一份注册表同步计划")
def plan_generated(run_cli: RunCli, registry_plan: dict[str, str]) -> None:
    outcome = run_cli("registry", "update")
    assert outcome.code == 0, outcome.data
    registry_plan["planId"] = outcome.data["planId"]


@given("该同步计划已被应用")
def plan_applied(run_cli: RunCli, registry_plan: dict[str, str]) -> None:
    outcome = run_cli("registry", "apply", "--plan", registry_plan["planId"])
    assert outcome.code == 0 and outcome.data["applied"] is True, outcome.data


@given("注册表全局存储被清空")
def store_cleared(isolated_registry_store: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    shutil.rmtree(isolated_registry_store)
    monkeypatch.setattr(registry_store, "_VERIFIED", set())
    monkeypatch.setattr(registry_store, "_SNAPSHOTS", {})


@given(parsers.parse('需求 "{name}" 已确认一份只含需求与设计的 Plan'))
def docs_plan_approved(home: Path, name: str) -> None:
    create_approved(home, DOCS_FLOW, name)


@given(parsers.parse('项目内保留了 Profile "{name}" 的副本'))
def vendored_profile(home: Path, name: str) -> None:
    (home / "profiles").mkdir(exist_ok=True)
    (home / "profiles" / f"{name}.yaml").write_text("vendored\n")


# --- when -----------------------------------------------------------------------------


@when("用户检查注册表更新")
def check_update(run_cli: RunCli, last_call: LastCall) -> None:
    last_call.outcome = run_cli("registry", "update")


@when(parsers.parse('用户获取节点 "{node}" 的指令'))
def node_instruction(run_cli: RunCli, last_call: LastCall, node: str) -> None:
    last_call.outcome = run_cli("node", "instructions", "-c", "AFD1111", "-n", node)


@when(parsers.parse('用户删除项目内的 "{relative}" 后列出所有 Fragment'))
def remove_then_list(home: Path, run_cli: RunCli, last_call: LastCall, relative: str) -> None:
    (home / relative).unlink()
    last_call.outcome = run_cli("fragment", "list")


# --- then -----------------------------------------------------------------------------


@then("返回了同步计划编号")
def plan_id_returned(last_call: LastCall) -> None:
    data = outcome_of(last_call).data
    plan_id = data.get("planId")
    assert isinstance(plan_id, str) and plan_id, data


@then(parsers.parse('工作流 home 中没有 "{name}"'))
def file_absent(home: Path, name: str) -> None:
    assert not (home / name).exists()


@then(parsers.re(r'Fragment "(?P<name>[^"]+)" 的注册表来源版本为 "(?P<tag>[^"]+)"'))
def fragment_synced_tag(last_call: LastCall, name: str, tag: str) -> None:
    fragments = {item["name"]: item for item in outcome_of(last_call).data["fragments"]}
    assert fragments[name]["source"] == "registry", fragments[name]
    assert fragments[name]["registry"]["syncedTag"] == tag, fragments[name]


@then(parsers.parse('返回的指令与注册表中 "{relative}" 一致'))
def instruction_matches_registry(
    last_call: LastCall, registry_source: dict[str, Path], relative: str
) -> None:
    expected = (registry_source["path"] / relative).read_text()
    assert outcome_of(last_call).data["instruction"] == expected
