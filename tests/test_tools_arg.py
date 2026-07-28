import pytest

from loopspec.errors import ConfigValidationError
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
