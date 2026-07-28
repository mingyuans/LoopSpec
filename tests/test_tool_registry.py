from pathlib import Path

import pytest

from loopspec.tool_registry import (
    AI_TOOLS,
    COMMAND_ADAPTERS,
    CommandContent,
    is_registered_tool,
)


def test_registered_tool_can_be_queried():
    assert AI_TOOLS["claude"].skills_dir == ".claude"


def test_all_five_v1_tools_registered():
    assert set(AI_TOOLS) == {"claude", "codex", "opencode", "cursor", "windsurf"}


def test_unregistered_tool_is_detected():
    assert is_registered_tool("claude") is True
    assert is_registered_tool("not-a-real-tool") is False


def make_content() -> CommandContent:
    return CommandContent(
        id="new",
        name="/lpsx:new",
        description="Create a new change",
        body="Run `loopspec new <change-name>`, then continue with `loopspec status`.",
    )


def test_claude_command_path_and_naming(tmp_path: Path):
    adapter = COMMAND_ADAPTERS["claude"]
    path = adapter.get_file_path(tmp_path, "new")
    assert path == tmp_path / ".claude" / "commands" / "lpsx" / "new.md"

    formatted = adapter.format_file(make_content())
    assert "/lpsx:new" in formatted
    assert "loopspec new <change-name>" in formatted


def test_codex_command_path_is_global_not_project_local(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("CODEX_HOME", raising=False)
    adapter = COMMAND_ADAPTERS["codex"]
    path = adapter.get_file_path(tmp_path, "new")
    assert path == Path.home() / ".codex" / "prompts" / "lpsx-new.md"
    assert tmp_path not in path.parents


def test_codex_home_env_var_overrides_default(tmp_path: Path, monkeypatch):
    custom_home = tmp_path / "custom-codex-home"
    monkeypatch.setenv("CODEX_HOME", str(custom_home))
    adapter = COMMAND_ADAPTERS["codex"]
    path = adapter.get_file_path(tmp_path, "new")
    assert path == custom_home / "prompts" / "lpsx-new.md"


@pytest.mark.parametrize(
    "tool_id,tool_dir",
    [("opencode", ".opencode"), ("cursor", ".cursor"), ("windsurf", ".windsurf")],
)
def test_hyphenated_tools_command_path_and_naming(tmp_path: Path, tool_id: str, tool_dir: str):
    adapter = COMMAND_ADAPTERS[tool_id]
    path = adapter.get_file_path(tmp_path, "archive")
    assert path == tmp_path / tool_dir / "commands" / "lpsx-archive.md"


def test_same_content_different_frontmatter_same_body():
    content = make_content()
    claude_output = COMMAND_ADAPTERS["claude"].format_file(content)
    codex_output = COMMAND_ADAPTERS["codex"].format_file(content)

    assert claude_output != codex_output
    assert content.body in claude_output
    assert content.body in codex_output
    assert "name:" in claude_output
    assert "name:" not in codex_output
