"""Steps for `loopspec fragment` / `loopspec profile`."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
import yaml
from pytest_bdd import given, parsers, then, when

from tests.conftest import QA_FLOW_ONE_RETRY, CliOutcome, LastCall
from tests.steps.common import outcome_of
from tests.workflow_helpers import CHANGE, create_approved

RunCli = Callable[..., CliOutcome]
MARKER = b"# marker: must survive a refused save\n"


@pytest.fixture
def profile_bytes() -> dict[str, bytes]:
    """A saved Profile's bytes after the marker was appended, keyed by its relative path."""
    return {}


def names(last_call: LastCall, key: str) -> set[str]:
    return {item["name"] for item in outcome_of(last_call).data[key]}


# --- given ----------------------------------------------------------------------------


@given(parsers.re(r'Fragment "(?P<name>[^"]+)" 的定义追加了已移除字段 "(?P<line>[^"]+)"'))
def fragment_with_removed_field(home: Path, name: str, line: str) -> None:
    path = home / "fragments" / name / "fragment.yaml"
    assert path.is_file(), path
    path.write_text(path.read_text() + line + "\n")
    assert path.read_text().endswith(line + "\n")


@given("隔离项目中有一个带 on_fail 的已批准 Plan")
def approved_qa_plan(home: Path) -> None:
    create_approved(home, QA_FLOW_ONE_RETRY)


@given(parsers.re(r'Profile 文件 "(?P<relative>[^"]+)" 末尾已追加一行标记'))
def profile_marked(home: Path, profile_bytes: dict[str, bytes], relative: str) -> None:
    path = home / relative
    assert path.is_file(), path
    path.write_bytes(path.read_bytes() + MARKER)
    profile_bytes[relative] = path.read_bytes()
    assert profile_bytes[relative].endswith(MARKER)


# --- when -----------------------------------------------------------------------------


@when(parsers.re(r'用户查看 Fragment "(?P<name>[^"]+)"'))
def show_fragment(run_cli: RunCli, last_call: LastCall, name: str) -> None:
    last_call.outcome = run_cli("fragment", "show", name)


@when(parsers.re(r'用户校验 Fragment "(?P<name>[^"]+)"'))
def validate_fragment(run_cli: RunCli, last_call: LastCall, name: str) -> None:
    last_call.outcome = run_cli("fragment", "validate", name)


@when("用户列出所有 Profile")
def list_profiles(run_cli: RunCli, last_call: LastCall) -> None:
    last_call.outcome = run_cli("profile", "list")


@when(parsers.re(r'用户把当前 Change 的流程保存为 Profile "(?P<name>[^"]+)"'))
def save_profile(run_cli: RunCli, last_call: LastCall, name: str) -> None:
    last_call.outcome = run_cli("profile", "save", name, "-c", CHANGE)


# --- then -----------------------------------------------------------------------------


@then(parsers.re(r'Fragment 列表包含 "(?P<name>[^"]+)"'))
def fragment_listed(last_call: LastCall, name: str) -> None:
    assert name in names(last_call, "fragments")


@then(parsers.re(r'Profile 列表恰好是 "(?P<expected>[^"]+)"'))
def profiles_exactly(last_call: LastCall, expected: str) -> None:
    assert names(last_call, "profiles") == set(expected.split(","))


@then(parsers.re(r'Profile 文件 "(?P<relative>[^"]+)" 保留了 qa 节点的 on_fail'))
def saved_profile_keeps_on_fail(home: Path, relative: str) -> None:
    saved = yaml.safe_load((home / relative).read_text())
    qa = next(node for node in saved["flow"] if node["id"] == "qa")
    expected = next(node for node in QA_FLOW_ONE_RETRY if node["id"] == "qa")
    assert qa["on_fail"] == expected["on_fail"]
    assert not {"protected", "min_engine_version", "meta", "nodes"} & set(saved)


@then(parsers.re(r'Profile 文件 "(?P<relative>[^"]+)" 与追加标记后逐字节一致'))
def profile_untouched(home: Path, profile_bytes: dict[str, bytes], relative: str) -> None:
    assert (home / relative).read_bytes() == profile_bytes[relative]
