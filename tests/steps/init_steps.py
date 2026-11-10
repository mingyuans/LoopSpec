"""Steps for `loopspec init`; everything stays inside the scenario's tmp_path."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
from pytest_bdd import given, parsers, then, when

from tests.conftest import CliOutcome, LastCall
from tests.steps.common import outcome_of

RunApp = Callable[..., CliOutcome]
CUSTOMIZED = "customized by the user\n"


@pytest.fixture
def project_root(tmp_path: Path, isolated_codex_home: Path) -> Path:
    """The project the user runs init in; Codex's global prompts are redirected to tmp_path."""
    root = tmp_path / "proj"
    root.mkdir()
    return root


@pytest.fixture
def workflow_home(project_root: Path) -> Path:
    return project_root / "wf"


# --- setup ----------------------------------------------------------------------------


@given("一个尚未初始化的项目目录")
def fresh_project(workflow_home: Path) -> None:
    assert not workflow_home.exists()


@given(parsers.re(r'工作流目录已初始化，且删除了 Profile "(?P<profile>[^"]+)"'))
def initialized_without_profile(run_app: RunApp, workflow_home: Path, profile: str) -> None:
    outcome = run_app("init", str(workflow_home), "--json")
    assert outcome.code == 0, outcome.data
    (workflow_home / "profiles" / f"{profile}.yaml").unlink()


@given(parsers.re(r'Profile "(?P<profile>[^"]+)" 已被用户定制'))
def profile_customized(workflow_home: Path, profile: str) -> None:
    path = workflow_home / "profiles" / f"{profile}.yaml"
    assert path.is_file()
    path.write_text(CUSTOMIZED)


# --- actions --------------------------------------------------------------------------


@when("用户以 JSON 模式初始化工作流目录")
def init_json(run_app: RunApp, last_call: LastCall, workflow_home: Path) -> None:
    last_call.outcome = run_app("init", str(workflow_home), "--json")


@when("用户以 JSON 模式初始化工作流目录并更新资源")
def init_update_resources(run_app: RunApp, last_call: LastCall, workflow_home: Path) -> None:
    last_call.outcome = run_app("init", str(workflow_home), "--json", "--update-resources")


@when(parsers.re(r'用户以 JSON 模式初始化工作流目录并配置工具 "(?P<tools>[^"]+)"'))
def init_with_tools(run_app: RunApp, last_call: LastCall, workflow_home: Path, tools: str) -> None:
    last_call.outcome = run_app("init", str(workflow_home), "--tools", tools, "--json")


# --- outcomes -------------------------------------------------------------------------


@then("工作流目录中有 config.yaml 和空的 memory 目录")
def config_and_memory(workflow_home: Path) -> None:
    assert (workflow_home / "config.yaml").is_file()
    memory = workflow_home / "memory"
    assert memory.is_dir() and not any(memory.iterdir())


@then("工作流目录中有内置的 Fragment 与 Profile")
def builtin_resources(workflow_home: Path, last_call: LastCall) -> None:
    assert (workflow_home / "fragments/requirements/fragment.yaml").is_file()
    assert (workflow_home / "profiles/bugfix.yaml").is_file()
    assert outcome_of(last_call).data["copiedWorkflowResources"]


@then(parsers.re(r'Profile "(?P<profile>[^"]+)" 仍不存在'))
def profile_still_missing(workflow_home: Path, last_call: LastCall, profile: str) -> None:
    assert not (workflow_home / "profiles" / f"{profile}.yaml").exists()
    assert outcome_of(last_call).data["copiedWorkflowResources"] == []


@then(parsers.parse('本次只复制了 "{resource}"'))
def only_copied(workflow_home: Path, last_call: LastCall, resource: str) -> None:
    assert outcome_of(last_call).data["copiedWorkflowResources"] == [resource]
    assert (workflow_home / resource).is_file()


@then(parsers.re(r'Profile "(?P<profile>[^"]+)" 保持用户定制的内容'))
def profile_kept(workflow_home: Path, profile: str) -> None:
    assert (workflow_home / "profiles" / f"{profile}.yaml").read_text() == CUSTOMIZED


@then(parsers.parse('项目根目录下有 "{relative}"'))
def file_under_project_root(project_root: Path, last_call: LastCall, relative: str) -> None:
    assert outcome_of(last_call).data["projectRoot"] == str(project_root.resolve())
    assert (project_root / relative).is_file()


@then(parsers.parse('工作流目录内没有 "{relative}"'))
def nothing_in_home(workflow_home: Path, relative: str) -> None:
    assert not (workflow_home / relative).exists()


@then(parsers.parse('"{tool}" 的 Hook 状态为 "{status}"'))
def hook_status(last_call: LastCall, tool: str, status: str) -> None:
    hooks = outcome_of(last_call).data["hooks"]
    assert hooks[tool]["status"] == status, hooks


# --- generated skills: the memory rules an Agent follows ------------------------------

MAINTENANCE_START = "Memory maintenance procedure."
MAINTENANCE_END = "without inventing writes or test results."


def skill_text(project_root: Path, skill: str) -> str:
    return (project_root / ".claude" / "skills" / skill / "SKILL.md").read_text(encoding="utf-8")


def maintenance_procedure(text: str) -> str:
    start = text.index(MAINTENANCE_START)
    return text[start : text.index(MAINTENANCE_END, start) + len(MAINTENANCE_END)]


@then(parsers.re(r'技能 "(?P<skill>[^"]+)" 只在用户要求归档时复查 memory，且先预览归档'))
def archive_skill_memory_rules(project_root: Path, skill: str) -> None:
    text = skill_text(project_root, skill)
    assert "only when the user has requested archiving" in text
    assert "tidying memory is not itself authorization to archive" in text
    assert text.index("--dry-run") < text.index("Memory review")
    assert "report `No memory update` and continue" in text


@then(parsers.re(r'技能 "(?P<skill>[^"]+)" 只在约定事件发生时更新 memory，且不作为推进前提'))
def continue_skill_memory_rules(project_root: Path, skill: str) -> None:
    text = skill_text(project_root, skill)
    assert "Update memory only when one of these has actually happened" in text
    for event in (
        "the user explicitly corrected you",
        "a root cause or fix was verified by real evidence",
        "a review conclusion was settled",
        "a key agreement was made",
    ):
        assert event in text, event
    assert "writing memory is never a prerequisite for advancing or completing a node" in text


@then(parsers.re(r'技能 "(?P<first>[^"]+)" 与 "(?P<second>[^"]+)" 的 memory 维护流程逐字相同'))
def shared_maintenance_procedure(project_root: Path, first: str, second: str) -> None:
    one = maintenance_procedure(skill_text(project_root, first))
    other = maintenance_procedure(skill_text(project_root, second))
    assert one == other and len(one) > 1500
