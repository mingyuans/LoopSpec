"""`loopspec init` merges the plan-guard PreToolUse hook into Claude Code and Codex configs."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from typer.testing import CliRunner

from loopspec.cli import app
from loopspec.scaffold import HOOK_COMMAND, install_hooks

runner = CliRunner()

FILES = {"claude": ".claude/settings.json", "codex": ".codex/hooks.json"}


@pytest.fixture(autouse=True)
def isolated_codex_home(tmp_path: Path, monkeypatch) -> Path:
    home = tmp_path / "codex-home"
    monkeypatch.setenv("CODEX_HOME", str(home))
    return home


def commands(data: dict) -> list[str]:
    return [hook["command"] for entry in data["hooks"]["PreToolUse"] for hook in entry["hooks"]]


@pytest.mark.parametrize("tool", ["claude", "codex"])
def test_creates_config(tmp_path: Path, tool: str):
    result = install_hooks(tmp_path, [tool])
    path = tmp_path / FILES[tool]
    assert result[tool] == {"path": str(path), "status": "created"}
    data = json.loads(path.read_text())
    assert commands(data) == [HOOK_COMMAND]
    matcher = data["hooks"]["PreToolUse"][0]["matcher"]
    expected = (
        "Edit|MultiEdit|Write|NotebookEdit|Bash" if tool == "claude" else "^apply_patch$|^Bash$"
    )
    assert matcher == expected


@pytest.mark.parametrize("tool", ["claude", "codex"])
def test_merges_and_keeps_existing_settings(tmp_path: Path, tool: str):
    path = tmp_path / FILES[tool]
    path.parent.mkdir()
    existing = {
        "model": "x",
        "hooks": {
            "PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": "mine"}]}],
            "Stop": [{"hooks": [{"type": "command", "command": "bye"}]}],
        },
    }
    path.write_text(json.dumps(existing))
    assert install_hooks(tmp_path, [tool])[tool]["status"] == "updated"
    data = json.loads(path.read_text())
    assert data["model"] == "x" and data["hooks"]["Stop"] == existing["hooks"]["Stop"]
    assert commands(data) == ["mine", HOOK_COMMAND]


@pytest.mark.parametrize("tool", ["claude", "codex"])
def test_rerun_is_unchanged(tmp_path: Path, tool: str):
    install_hooks(tmp_path, [tool])
    before = (tmp_path / FILES[tool]).read_bytes()
    assert install_hooks(tmp_path, [tool])[tool]["status"] == "unchanged"
    assert (tmp_path / FILES[tool]).read_bytes() == before


@pytest.mark.parametrize(
    "content", ["{not json", "[]", '{"hooks": []}', '{"hooks": {"PreToolUse": {}}}']
)
def test_invalid_config_is_skipped_untouched(tmp_path: Path, content: str):
    path = tmp_path / FILES["claude"]
    path.parent.mkdir()
    path.write_text(content)
    result = install_hooks(tmp_path, ["claude"])["claude"]
    assert result["status"] == "skipped" and result["reason"]
    assert path.read_text() == content


def test_symlinked_config_is_skipped(tmp_path: Path):
    target = tmp_path / "real.json"
    target.write_text("{}")
    (tmp_path / ".claude").mkdir()
    os.symlink(target, tmp_path / FILES["claude"])
    assert install_hooks(tmp_path, ["claude"])["claude"]["status"] == "skipped"
    assert target.read_text() == "{}"


def test_other_tools_get_no_hook(tmp_path: Path):
    assert install_hooks(tmp_path, ["opencode"]) == {}
    assert not (tmp_path / ".claude").exists() and not (tmp_path / ".codex").exists()


def test_init_reports_hooks(tmp_path: Path):
    project_root = tmp_path / "proj"
    project_root.mkdir()
    result = runner.invoke(
        app, ["init", str(project_root / "wf"), "--tools", "claude,codex", "--json"]
    )
    assert result.exit_code == 0, result.stdout
    data = json.loads(result.stdout)
    assert data["hooks"]["claude"]["status"] == "created"
    assert data["hooks"]["codex"]["status"] == "created"
    assert (project_root / FILES["claude"]).is_file() and (project_root / FILES["codex"]).is_file()


def test_init_without_claude_or_codex_writes_no_hook(tmp_path: Path):
    project_root = tmp_path / "proj"
    project_root.mkdir()
    result = runner.invoke(app, ["init", str(project_root / "wf"), "--json"])
    assert json.loads(result.stdout)["hooks"] == {}
    assert not (project_root / ".claude").exists()


def test_init_text_output_mentions_codex_trust(tmp_path: Path):
    project_root = tmp_path / "proj"
    project_root.mkdir()
    result = runner.invoke(app, ["init", str(project_root / "wf"), "--tools", "codex"])
    assert result.exit_code == 0
    assert "/hooks" in result.stdout
