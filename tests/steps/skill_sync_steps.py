"""Steps for features/skill_sync.feature: workflow commands sync the project's skills."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from pytest_bdd import given, parsers, then, when
from typer.testing import CliRunner

from loopspec.cli import app
from loopspec.scaffold import expected_files, scaffold_tools
from tests.conftest import CliOutcome, LastCall
from tests.steps.common import outcome_of

runner = CliRunner()


def skill(root: Path, name: str) -> Path:
    return root / ".claude/skills" / name / "SKILL.md"


@pytest.fixture
def outside_file(tmp_path: Path) -> Path:
    return tmp_path / "outside-skill.md"


@given("项目已用 loopspec init 配置了 claude 的 skill")
def claude_configured(home: Path) -> None:
    scaffold_tools(home.parent, ["claude"])
    assert skill(home.parent, "loopspec-new").is_file()


@given(parsers.re(r'项目中的 skill "(?P<name>[a-z-]+)" 是旧版本内容'))
def stale_skill(home: Path, name: str) -> None:
    skill(home.parent, name).write_text("an older loopspec skill\n")


@given(parsers.re(r'项目中缺少 skill "(?P<name>[a-z-]+)"'))
def missing_skill(home: Path, name: str) -> None:
    skill(home.parent, name).unlink()


@given(parsers.re(r'项目中的 skill "(?P<name>[a-z-]+)" 是指向项目外文件的符号链接'))
def symlinked_skill(home: Path, outside_file: Path, name: str) -> None:
    outside_file.write_text("outside\n")
    path = skill(home.parent, name)
    path.unlink()
    os.symlink(outside_file, path)


@when(parsers.re(r'在项目中新建 Change "(?P<change>[A-Za-z0-9-]+)"'))
def new_change_with_stderr(home: Path, last_call: LastCall, change: str) -> None:
    result = runner.invoke(app, ["change", "new", change, "--json", "--home", str(home)])
    data = json.loads(result.stdout) if result.stdout.strip() else {}
    last_call.outcome = CliOutcome(result.exit_code, data, output=result.stderr)


@then(parsers.re(r'skill "(?P<name>[a-z-]+)" 与 CLI 内置内容一致'))
def skill_matches_cli(home: Path, name: str) -> None:
    path = skill(home.parent, name)
    assert path.read_text() == expected_files(home.parent, "claude")[path]


@then(parsers.re(r"stderr 提示同步了 (?P<count>\d+) 个 skill 文件"))
def stderr_reports_sync(last_call: LastCall, count: str) -> None:
    assert f"synced {count} skill file(s)" in outcome_of(last_call).output


@then("stderr 没有同步提示")
def stderr_silent(last_call: LastCall) -> None:
    assert "loopspec:" not in outcome_of(last_call).output


@then(parsers.re(r'项目中没有为未配置的工具 "(?P<tool>[a-z-]+)" 创建文件'))
def tool_not_created(home: Path, tool: str) -> None:
    assert not (home.parent / f".{tool}").exists()


@then("项目外的文件没有被改写")
def outside_untouched(outside_file: Path) -> None:
    assert outside_file.read_text() == "outside\n"


@then(parsers.re(r'stderr 告警无法同步 skill "(?P<name>[a-z-]+)"'))
def stderr_warns(last_call: LastCall, name: str) -> None:
    output = outcome_of(last_call).output
    assert "could not sync" in output and f"skills/{name}/SKILL.md" in output
