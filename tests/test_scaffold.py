from pathlib import Path

from loopspec.scaffold import scaffold_tools
from loopspec.tool_registry import AI_TOOLS, ToolSpec


def test_single_tool_writes_four_skills_and_four_commands(tmp_path: Path):
    result = scaffold_tools(tmp_path, ["claude"])

    skill_dirs = sorted((tmp_path / ".claude" / "skills").iterdir())
    assert len(skill_dirs) == 4
    for d in skill_dirs:
        assert (d / "SKILL.md").is_file()

    command_files = sorted((tmp_path / ".claude" / "commands" / "lpsx").glob("*.md"))
    assert len(command_files) == 4

    assert len(result.written_files["claude"]) == 8
    assert result.skipped_command_generation == []


def test_multi_tool_writes_files_for_each(tmp_path: Path):
    result = scaffold_tools(tmp_path, ["claude", "opencode"])

    assert (tmp_path / ".claude" / "skills" / "loopspec-new" / "SKILL.md").is_file()
    assert (tmp_path / ".opencode" / "skills" / "loopspec-new" / "SKILL.md").is_file()
    assert (tmp_path / ".opencode" / "commands" / "lpsx-new.md").is_file()
    assert set(result.written_files) == {"claude", "opencode"}


def test_repeated_call_overwrites_without_error(tmp_path: Path):
    scaffold_tools(tmp_path, ["claude"])
    skill_file = tmp_path / ".claude" / "skills" / "loopspec-new" / "SKILL.md"
    skill_file.write_text("stale hand-edited content")

    scaffold_tools(tmp_path, ["claude"])
    assert "stale hand-edited content" not in skill_file.read_text()


def test_tool_without_command_adapter_skips_commands_but_writes_skills(
    tmp_path: Path, monkeypatch
):
    monkeypatch.setitem(
        AI_TOOLS, "no-adapter-tool", ToolSpec(id="no-adapter-tool", skills_dir=".noadapter")
    )

    result = scaffold_tools(tmp_path, ["no-adapter-tool"])

    skill_dirs = list((tmp_path / ".noadapter" / "skills").iterdir())
    assert len(skill_dirs) == 4
    assert not (tmp_path / ".noadapter" / "commands").exists()
    assert result.skipped_command_generation == ["no-adapter-tool"]
    assert len(result.written_files["no-adapter-tool"]) == 4


def test_no_tool_selection_manifest_written(tmp_path: Path):
    scaffold_tools(tmp_path, ["claude"])

    all_files = {p.name for p in tmp_path.rglob("*") if p.is_file()}
    assert all(name == "SKILL.md" or name.endswith(".md") for name in all_files)
    assert not any(
        "tool" in name.lower() and name.endswith((".json", ".yaml", ".yml")) for name in all_files
    )
