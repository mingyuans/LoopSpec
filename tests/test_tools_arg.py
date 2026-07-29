from pathlib import Path

import pytest

from loopspec.errors import ConfigValidationError
from loopspec.scaffold import scaffold_tools
from loopspec.tool_registry import AI_TOOLS
from loopspec.tools_cli import prompt_tools_interactively, resolve_tools_arg


def test_none_raw_returns_empty_list():
    assert resolve_tools_arg(None) == []


def test_none_keyword_returns_empty_list():
    assert resolve_tools_arg("none") == []
    assert resolve_tools_arg("None") == []


def test_all_keyword_returns_every_registered_tool():
    assert resolve_tools_arg("all") == sorted(AI_TOOLS)


def test_subset_parsed_case_insensitively():
    assert resolve_tools_arg("Claude,CODEX") == ["claude", "codex"]


def test_duplicate_ids_deduped_preserving_order():
    assert resolve_tools_arg("claude,claude,codex") == ["claude", "codex"]


def test_unknown_tool_id_raises_with_valid_ids_in_fix():
    with pytest.raises(ConfigValidationError) as exc_info:
        resolve_tools_arg("claude,not-a-real-tool")
    assert "not-a-real-tool" in str(exc_info.value)
    assert "claude" in exc_info.value.fix


def test_interactive_prompt_all():
    result = prompt_tools_interactively(input_fn=lambda _: "all", print_fn=lambda _: None)
    assert result == sorted(AI_TOOLS)


def test_interactive_prompt_none_on_empty_reply():
    result = prompt_tools_interactively(input_fn=lambda _: "", print_fn=lambda _: None)
    assert result == []


def test_interactive_prompt_numbered_selection():
    ids = sorted(AI_TOOLS)
    claude_index = ids.index("claude") + 1
    codex_index = ids.index("codex") + 1
    result = prompt_tools_interactively(
        input_fn=lambda _: f"{claude_index},{codex_index}", print_fn=lambda _: None
    )
    assert result == ["claude", "codex"]


def test_interactive_prompt_invalid_number_raises():
    with pytest.raises(ConfigValidationError):
        prompt_tools_interactively(input_fn=lambda _: "999", print_fn=lambda _: None)


def capture_prompt(project_path, reply: str) -> tuple[list[str], list[str]]:
    lines: list[str] = []
    selected = prompt_tools_interactively(
        project_path, input_fn=lambda _: reply, print_fn=lines.append
    )
    return selected, lines


def test_configured_tool_is_labelled_and_refresh_is_announced(tmp_path: Path):
    scaffold_tools(tmp_path, ["claude"])
    ids = sorted(AI_TOOLS)
    selected, lines = capture_prompt(tmp_path, str(ids.index("claude") + 1))

    assert selected == ["claude"]
    assert any(line.strip() == f"{ids.index('claude') + 1}) claude (configured)" for line in lines)
    assert "Selected: claude (refresh)" in lines


def test_unconfigured_tool_has_no_label(tmp_path: Path):
    scaffold_tools(tmp_path, ["claude"])
    ids = sorted(AI_TOOLS)
    _, lines = capture_prompt(tmp_path, "none")

    codex_line = next(line for line in lines if line.strip().endswith("codex"))
    assert codex_line.strip() == f"{ids.index('codex') + 1}) codex"


def test_detected_directory_without_skills_is_labelled_detected(tmp_path: Path):
    (tmp_path / ".cursor").mkdir()
    _, lines = capture_prompt(tmp_path, "none")
    assert any(line.strip().endswith("cursor (detected)") for line in lines)


def test_labels_do_not_affect_number_parsing(tmp_path: Path):
    scaffold_tools(tmp_path, ["claude"])
    ids = sorted(AI_TOOLS)
    reply = f"{ids.index('claude') + 1},{ids.index('codex') + 1}"
    selected, lines = capture_prompt(tmp_path, reply)

    assert selected == ["claude", "codex"]
    assert "Selected: claude (refresh), codex" in lines


def test_all_reply_still_announces_refreshes(tmp_path: Path):
    scaffold_tools(tmp_path, ["claude"])
    selected, lines = capture_prompt(tmp_path, "all")

    assert selected == sorted(AI_TOOLS)
    assert any("claude (refresh)" in line for line in lines)


def test_no_project_path_means_no_labels():
    lines: list[str] = []
    prompt_tools_interactively(input_fn=lambda _: "none", print_fn=lines.append)
    assert not any("(configured)" in line or "(detected)" in line for line in lines)
