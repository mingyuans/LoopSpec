from pathlib import Path

import pytest

from loopspec.tool_registry import (
    AI_TOOLS,
    COMMAND_ADAPTERS,
    CommandContent,
    ToolSpec,
    is_registered_tool,
)
from loopspec.tools_cli import tool_is_detected

EXPECTED_TOOL_COUNT = 31


def test_registered_tool_can_be_queried():
    assert AI_TOOLS["claude"].skills_dir == ".claude"
    assert AI_TOOLS["claude"].label == "Claude Code"


def test_registry_holds_the_full_tool_set():
    assert len(AI_TOOLS) == EXPECTED_TOOL_COUNT


@pytest.mark.parametrize("tool_id", sorted(AI_TOOLS))
def test_every_tool_has_a_skills_dir_and_display_name(tool_id: str):
    tool = AI_TOOLS[tool_id]
    assert tool.id == tool_id, "the dict key must match the spec's own id"
    assert tool.skills_dir.startswith("."), tool.skills_dir
    assert tool.display_name, f"{tool_id} has no display name"


def test_skills_dirs_are_unique():
    """A shared `skills_dir` would make two tools overwrite each other's skills."""

    dirs = [tool.skills_dir for tool in AI_TOOLS.values()]
    assert len(set(dirs)) == len(dirs), "duplicate skills_dir in the registry"


def test_display_name_falls_back_to_id_when_undeclared():
    assert ToolSpec(id="brand-new", skills_dir=".brand-new").label == "brand-new"


def test_unregistered_tool_is_detected():
    assert is_registered_tool("claude") is True
    assert is_registered_tool("not-a-real-tool") is False


# --------------------------------------------------------------------------- #
# detection (task 2.6)
# --------------------------------------------------------------------------- #


def test_tool_with_own_dotdir_is_detected_by_directory(tmp_path: Path):
    (tmp_path / ".cursor").mkdir()
    assert tool_is_detected(tmp_path, "cursor") is True
    assert tool_is_detected(tmp_path, "windsurf") is False


def test_copilot_is_not_detected_by_a_bare_github_dir(tmp_path: Path):
    """`.github/` exists in nearly every repo -- CI config is not Copilot."""

    (tmp_path / ".github" / "workflows").mkdir(parents=True)
    (tmp_path / ".github" / "workflows" / "ci.yml").write_text("on: push\n", encoding="utf-8")
    assert tool_is_detected(tmp_path, "github-copilot") is False


@pytest.mark.parametrize(
    "marker",
    [
        ".github/copilot-instructions.md",
        ".github/instructions",
        ".github/prompts",
        ".github/agents",
        ".github/skills",
        ".github/.mcp.json",
    ],
)
def test_copilot_detection_paths_each_count(tmp_path: Path, marker: str):
    target = tmp_path / marker
    if target.suffix:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("", encoding="utf-8")
    else:
        target.mkdir(parents=True)
    assert tool_is_detected(tmp_path, "github-copilot") is True


def test_nothing_on_disk_means_nothing_detected(tmp_path: Path):
    assert not any(tool_is_detected(tmp_path, tool_id) for tool_id in AI_TOOLS)


def make_content(name: str = "/lpsx:new") -> CommandContent:
    return CommandContent(
        id="new",
        name=name,
        description="Create a new change",
        body="Run `loopspec new <change-name>`, then continue with `loopspec status`.",
    )


# --------------------------------------------------------------------------- #
# on-disk layout, asserted as whole path strings (task 3.6)
#
# Getting one of these wrong writes a file somewhere the tool never reads, with
# no error anywhere -- so every tool is spelled out rather than sampled.
# --------------------------------------------------------------------------- #

SKILL_PATHS: dict[str, str] = {
    "amazon-q": ".amazonq/skills/loopspec-new/SKILL.md",
    "antigravity": ".agent/skills/loopspec-new/SKILL.md",
    "auggie": ".augment/skills/loopspec-new/SKILL.md",
    "bob": ".bob/skills/loopspec-new/SKILL.md",
    "claude": ".claude/skills/loopspec-new/SKILL.md",
    "cline": ".cline/skills/loopspec-new/SKILL.md",
    "codebuddy": ".codebuddy/skills/loopspec-new/SKILL.md",
    "codex": ".codex/skills/loopspec-new/SKILL.md",
    "continue": ".continue/skills/loopspec-new/SKILL.md",
    "costrict": ".cospec/skills/loopspec-new/SKILL.md",
    "crush": ".crush/skills/loopspec-new/SKILL.md",
    "cursor": ".cursor/skills/loopspec-new/SKILL.md",
    "factory": ".factory/skills/loopspec-new/SKILL.md",
    "forgecode": ".forge/skills/loopspec-new/SKILL.md",
    "gemini": ".gemini/skills/loopspec-new/SKILL.md",
    "github-copilot": ".github/skills/loopspec-new/SKILL.md",
    "iflow": ".iflow/skills/loopspec-new/SKILL.md",
    "junie": ".junie/skills/loopspec-new/SKILL.md",
    "kilocode": ".kilocode/skills/loopspec-new/SKILL.md",
    "kimi": ".kimi/skills/loopspec-new/SKILL.md",
    "kiro": ".kiro/skills/loopspec-new/SKILL.md",
    "lingma": ".lingma/skills/loopspec-new/SKILL.md",
    "oh-my-pi": ".omp/skills/loopspec-new/SKILL.md",
    "opencode": ".opencode/skills/loopspec-new/SKILL.md",
    "pi": ".pi/skills/loopspec-new/SKILL.md",
    "qoder": ".qoder/skills/loopspec-new/SKILL.md",
    "qwen": ".qwen/skills/loopspec-new/SKILL.md",
    "roocode": ".roo/skills/loopspec-new/SKILL.md",
    "trae": ".trae/skills/loopspec-new/SKILL.md",
    "vibe": ".vibe/skills/loopspec-new/SKILL.md",
    "windsurf": ".windsurf/skills/loopspec-new/SKILL.md",
}

#: Project-local command paths for verb `new`. `codex` is absent on purpose --
#: it writes outside the project, so it gets its own tests below.
COMMAND_PATHS: dict[str, str] = {
    "amazon-q": ".amazonq/prompts/lpsx-new.md",
    "antigravity": ".agent/workflows/lpsx-new.md",
    "auggie": ".augment/commands/lpsx-new.md",
    "bob": ".bob/commands/lpsx-new.md",
    "claude": ".claude/commands/lpsx/new.md",
    "cline": ".clinerules/workflows/lpsx-new.md",
    "codebuddy": ".codebuddy/commands/lpsx/new.md",
    "continue": ".continue/prompts/lpsx-new.prompt",
    "costrict": ".cospec/loopspec/commands/lpsx-new.md",
    "crush": ".crush/commands/lpsx/new.md",
    "cursor": ".cursor/commands/lpsx-new.md",
    "factory": ".factory/commands/lpsx-new.md",
    "gemini": ".gemini/commands/lpsx/new.toml",
    "github-copilot": ".github/prompts/lpsx-new.prompt.md",
    "iflow": ".iflow/commands/lpsx-new.md",
    "junie": ".junie/commands/lpsx-new.md",
    "kilocode": ".kilocode/workflows/lpsx-new.md",
    "kiro": ".kiro/prompts/lpsx-new.prompt.md",
    "lingma": ".lingma/commands/lpsx/new.md",
    "oh-my-pi": ".omp/commands/lpsx-new.md",
    "opencode": ".opencode/commands/lpsx-new.md",
    "pi": ".pi/prompts/lpsx-new.md",
    "qoder": ".qoder/commands/lpsx/new.md",
    "qwen": ".qwen/commands/lpsx-new.toml",
    "roocode": ".roo/commands/lpsx-new.md",
    "trae": ".trae/commands/lpsx-new.md",
    "windsurf": ".windsurf/workflows/lpsx-new.md",
}

TOOLS_WITHOUT_ADAPTER = {"forgecode", "kimi", "vibe"}


def test_skill_path_table_covers_every_registered_tool():
    assert set(SKILL_PATHS) == set(AI_TOOLS)


def test_command_path_table_covers_every_project_local_adapter():
    assert set(COMMAND_PATHS) == set(COMMAND_ADAPTERS) - {"codex"}


def test_tools_without_an_adapter_are_exactly_the_three_expected():
    assert set(AI_TOOLS) - set(COMMAND_ADAPTERS) == TOOLS_WITHOUT_ADAPTER


@pytest.mark.parametrize("tool_id", sorted(SKILL_PATHS))
def test_skill_path_is_exact(tmp_path: Path, tool_id: str):
    tool = AI_TOOLS[tool_id]
    path = tmp_path / tool.skills_dir / "skills" / "loopspec-new" / "SKILL.md"
    assert path == tmp_path / SKILL_PATHS[tool_id]


@pytest.mark.parametrize("tool_id", sorted(COMMAND_PATHS))
def test_command_path_is_exact(tmp_path: Path, tool_id: str):
    path = COMMAND_ADAPTERS[tool_id].get_file_path(tmp_path, "new")
    assert path == tmp_path / COMMAND_PATHS[tool_id]


def test_cline_keeps_skills_and_commands_in_separate_dirs(tmp_path: Path):
    """`.cline` vs `.clinerules` is the one tool where these genuinely differ;
    inferring one from the other writes commands where Cline never looks."""

    assert AI_TOOLS["cline"].skills_dir == ".cline"
    command_path = COMMAND_ADAPTERS["cline"].get_file_path(tmp_path, "new")
    assert command_path == tmp_path / ".clinerules" / "workflows" / "lpsx-new.md"
    assert ".cline/" not in str(command_path)


def test_costrict_nests_commands_under_a_loopspec_dir(tmp_path: Path):
    path = COMMAND_ADAPTERS["costrict"].get_file_path(tmp_path, "new")
    assert path == tmp_path / ".cospec" / "loopspec" / "commands" / "lpsx-new.md"


def test_copilot_and_kiro_use_a_double_extension(tmp_path: Path):
    assert COMMAND_ADAPTERS["github-copilot"].get_file_path(tmp_path, "new").name == (
        "lpsx-new.prompt.md"
    )
    assert COMMAND_ADAPTERS["kiro"].get_file_path(tmp_path, "new").name == "lpsx-new.prompt.md"


def test_continue_uses_a_bare_prompt_extension(tmp_path: Path):
    assert COMMAND_ADAPTERS["continue"].get_file_path(tmp_path, "new").name == "lpsx-new.prompt"


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


# --------------------------------------------------------------------------- #
# body formats (task 3.7)
# --------------------------------------------------------------------------- #


def test_claude_body_is_markdown_frontmatter():
    formatted = COMMAND_ADAPTERS["claude"].format_file(make_content())
    assert formatted.startswith("---\n")
    assert "name: /lpsx:new" in formatted
    assert "loopspec new <change-name>" in formatted


def test_cline_body_starts_with_a_heading_and_has_no_frontmatter():
    formatted = COMMAND_ADAPTERS["cline"].format_file(make_content("/lpsx-new"))
    assert formatted.startswith("# /lpsx-new")
    assert "---" not in formatted


@pytest.mark.parametrize("tool_id", ["gemini", "qwen"])
def test_toml_tools_emit_toml_not_markdown_frontmatter(tool_id: str):
    formatted = COMMAND_ADAPTERS[tool_id].format_file(make_content())
    assert formatted.startswith("description = ")
    assert "prompt = " in formatted
    assert not formatted.startswith("---")


def test_toml_body_is_parseable_and_round_trips_the_prompt():
    import tomllib

    content = make_content()
    parsed = tomllib.loads(COMMAND_ADAPTERS["gemini"].format_file(content))
    assert parsed["description"] == content.description
    assert content.body in parsed["prompt"]


def test_toml_body_escapes_a_triple_quote_in_the_prompt():
    """A raw triple quote would terminate the multi-line string early."""

    import tomllib

    hostile = CommandContent(id="x", name="/lpsx-x", description='say "hi"', body='a """ b')
    parsed = tomllib.loads(COMMAND_ADAPTERS["gemini"].format_file(hostile))
    assert parsed["description"] == 'say "hi"'
    assert '"""' in parsed["prompt"]


# --------------------------------------------------------------------------- #
# naming style vs. body (task 3.8)
# --------------------------------------------------------------------------- #


def test_same_content_different_frontmatter_same_body():
    content = make_content()
    claude_output = COMMAND_ADAPTERS["claude"].format_file(content)
    codex_output = COMMAND_ADAPTERS["codex"].format_file(content)

    assert claude_output != codex_output
    assert content.body in claude_output
    assert content.body in codex_output
    assert "name:" in claude_output
    assert "name:" not in codex_output


def test_namespaced_and_hyphenated_tools_differ_only_in_command_naming():
    """The instructions must be identical across tools; only `/lpsx:x` vs
    `/lpsx-x` may vary, which is what `hyphenated` drives."""

    from loopspec.skill_templates import SKILL_TEMPLATES, generate_command_content

    template = SKILL_TEMPLATES[1]  # `continue`, whose body cites other commands
    colon = generate_command_content(template, apply_hyphen_transform=False)
    hyphen = generate_command_content(template, apply_hyphen_transform=True)

    assert colon.name == "/lpsx:continue"
    assert hyphen.name == "/lpsx-continue"
    assert colon.body.replace("/lpsx:", "/lpsx-") == hyphen.body


@pytest.mark.parametrize("tool_id", sorted(COMMAND_ADAPTERS))
def test_hyphenated_flag_agrees_with_the_command_filename(tool_id: str, tmp_path: Path):
    """The single source of truth check: a tool that names files `lpsx-<verb>`
    must also rewrite `/lpsx:x` in the body, and vice versa."""

    adapter = COMMAND_ADAPTERS[tool_id]
    filename = adapter.get_file_path(tmp_path, "new").name
    assert adapter.hyphenated == filename.startswith("lpsx-new")
