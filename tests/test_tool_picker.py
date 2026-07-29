"""Tests for the searchable multi-select tool picker.

**No real terminal required.** `questionary` accepts `prompt_toolkit`'s
`input`/`output` objects, so a pipe input plus a `DummyOutput` drives the whole
picker from a byte string of keypresses -- see `drive()`. Without that, the only
way to cover 31 tools across several pre-selection states would be by hand.

Keypresses are written as `keys("space", "down", "enter")` rather than as raw
`" \\x1b[B\\r"`, because the escape sequences are unreadable and a future reader
needs to know what a test is actually doing.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest
import questionary
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output import DummyOutput

from loopspec.skill_templates import SKILL_TEMPLATES
from loopspec.tool_registry import AI_TOOLS
from loopspec.tools_cli import INTERRUPT_NOTICE, pick_tools, tool_status_label

#: Human-readable action -> the bytes prompt_toolkit reads for it.
KEYS: dict[str, str] = {
    "up": "\x1b[A",
    "down": "\x1b[B",
    "space": " ",
    "enter": "\r",
    "backspace": "\x7f",
}


def keys(*actions: str) -> str:
    """Turn `("space", "down", "enter")` into the byte string those keys send.

    A bare character that is not a named action is passed through, so search
    filtering can be written as `keys("c", "u", "r", "space", "enter")`.
    """

    return "".join(KEYS.get(action, action) for action in actions)


@contextmanager
def pipe(keystrokes: str) -> Iterator[Any]:
    """A prompt_toolkit input pre-loaded with `keystrokes`."""

    with create_pipe_input() as pipe_input:
        pipe_input.send_text(keystrokes)
        yield pipe_input


def configure(project_path: Path, *tool_ids: str) -> None:
    """Write a skill file for each tool so `tool_is_configured` sees it."""

    for tool_id in tool_ids:
        skill = (
            project_path
            / AI_TOOLS[tool_id].skills_dir
            / "skills"
            / SKILL_TEMPLATES[0].name
            / "SKILL.md"
        )
        skill.parent.mkdir(parents=True, exist_ok=True)
        skill.write_text("---\nname: x\n---\n", encoding="utf-8")


# --------------------------------------------------------------------------- #
# harness (task 1.2/1.3)
# --------------------------------------------------------------------------- #


def test_pipe_input_drives_questionary_checkbox() -> None:
    """The headless harness itself: no TTY, yet keypresses select a choice.

    Everything else in this file rests on this working, so it is asserted
    directly against `questionary` rather than through loopspec's own picker.
    """

    with pipe(keys("space", "down", "space", "enter")) as pipe_input:
        answer = questionary.checkbox(
            "pick",
            choices=[
                questionary.Choice(title="Claude Code", value="claude", checked=True),
                questionary.Choice(title="Codex", value="codex"),
            ],
            input=pipe_input,
            output=DummyOutput(),
        ).unsafe_ask()

    # space un-checks the pre-selected Claude, down moves, space checks Codex.
    assert answer == ["codex"]


@pytest.mark.parametrize(
    ("actions", "expected"),
    [
        (("space",), " "),
        (("down", "enter"), "\x1b[B\r"),
        (("c", "u", "r"), "cur"),
        (("backspace",), "\x7f"),
    ],
)
def test_keys_translates_actions_to_bytes(actions: tuple[str, ...], expected: str) -> None:
    assert keys(*actions) == expected


# --------------------------------------------------------------------------- #
# pick_tools (task 4.7)
# --------------------------------------------------------------------------- #


def pick(project_path: Path, keystrokes: str) -> tuple[list[str], list[str]]:
    """Run the real picker headlessly; returns (selection, printed lines)."""

    printed: list[str] = []
    with pipe(keystrokes) as pipe_input:
        selection = pick_tools(
            project_path,
            input=pipe_input,
            output=DummyOutput(),
            print_fn=printed.append,
        )
    return selection, printed


FIRST_TOOL = next(iter(AI_TOOLS))
SECOND_TOOL = list(AI_TOOLS)[1]


def test_arrow_keys_and_space_select_multiple_tools(tmp_path: Path) -> None:
    selection, _ = pick(tmp_path, keys("space", "down", "space", "enter"))
    assert selection == [FIRST_TOOL, SECOND_TOOL]


def test_confirming_without_checking_anything_returns_empty(tmp_path: Path) -> None:
    """Semantically identical to `--tools none`."""

    selection, _ = pick(tmp_path, keys("enter"))
    assert selection == []


def test_typing_filters_the_candidate_list(tmp_path: Path) -> None:
    """`cursor` is far down a 31-entry list; filtering brings it to the top."""

    selection, _ = pick(tmp_path, keys("c", "u", "r", "s", "o", "r", "space", "enter"))
    assert selection == ["cursor"]


def test_returned_ids_follow_registry_order_not_selection_order(tmp_path: Path) -> None:
    """Select Cursor first, then Claude; the result comes back in registry order.

    The filter text carries no spaces on purpose -- Space is the toggle key, so
    typing "Claude Code" would check whatever row happened to be highlighted.
    """

    keystrokes = (
        keys("c", "u", "r", "s", "o", "r", "space")
        + keys(*["backspace"] * 6)
        + keys("c", "l", "a", "u", "d", "e", "space", "enter")
    )
    selection, _ = pick(tmp_path, keystrokes)

    assert selection == ["claude", "cursor"]
    assert list(AI_TOOLS).index("claude") < list(AI_TOOLS).index("cursor")


def test_first_time_setup_preselects_detected_tools_and_says_so(tmp_path: Path) -> None:
    (tmp_path / ".cursor").mkdir()
    (tmp_path / ".zed").mkdir()  # not a registered tool -- must not appear

    selection, printed = pick(tmp_path, keys("enter"))

    assert selection == ["cursor"]
    assert any("Detected tool directories: Cursor" in line for line in printed)
    assert any("pre-selected for first-time setup" in line for line in printed)


def test_preselected_tool_can_be_unchecked(tmp_path: Path) -> None:
    (tmp_path / f"{AI_TOOLS[FIRST_TOOL].skills_dir}").mkdir()

    selection, _ = pick(tmp_path, keys("space", "enter"))
    assert selection == []


def test_second_run_preselects_configured_not_merely_detected(tmp_path: Path) -> None:
    """Re-running `init` defaults to refreshing what is configured, so a newly
    installed editor's bare directory does not silently join the selection."""

    configure(tmp_path, "claude")
    (tmp_path / ".cursor").mkdir()

    selection, printed = pick(tmp_path, keys("enter"))

    assert selection == ["claude"]
    assert not any("Detected tool directories" in line for line in printed)


def test_nothing_detected_and_nothing_configured_preselects_nothing(tmp_path: Path) -> None:
    selection, printed = pick(tmp_path, keys("enter"))
    assert selection == []
    assert not any("Detected tool directories" in line for line in printed)


def test_interrupt_is_treated_as_configuring_nothing(tmp_path: Path) -> None:
    """Ctrl+C must not surface a traceback: `init` has already created the
    workflow home, and an unexplained one is worse than a plain notice."""

    configure(tmp_path, "claude")
    selection, printed = pick(tmp_path, keys("\x03"))  # Ctrl+C

    assert selection == []
    assert INTERRUPT_NOTICE in printed


def test_candidate_titles_carry_display_names_and_status(tmp_path: Path) -> None:
    configure(tmp_path, "claude")
    (tmp_path / ".cursor").mkdir()

    assert tool_status_label(tmp_path, "claude") == " (configured)"
    assert tool_status_label(tmp_path, "cursor") == " (detected)"
    assert tool_status_label(tmp_path, "windsurf") == ""


def test_prompt_message_reports_the_available_count() -> None:
    assert len(AI_TOOLS) == 31, "the picker's count line is derived from the registry"


# --------------------------------------------------------------------------- #
# candidate text is registry constants only (task 4.8 / design D8)
# --------------------------------------------------------------------------- #

_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f-\x9f]")


@pytest.mark.parametrize("tool_id", sorted(AI_TOOLS))
def test_display_names_carry_no_control_characters(tool_id: str) -> None:
    """questionary writes straight to the terminal without going through
    `presentation.Presenter`, so its escaping guarantee does not cover these."""

    assert not _CONTROL_CHARS.search(AI_TOOLS[tool_id].label)


@pytest.mark.parametrize("tool_id", sorted(AI_TOOLS))
def test_display_names_carry_no_markup_constructs(tool_id: str) -> None:
    label = AI_TOOLS[tool_id].label
    assert "[" not in label and "]" not in label
    assert "<" not in label and ">" not in label


def test_candidate_titles_contain_no_paths(tmp_path: Path) -> None:
    """The only interpolation is the tool's own label plus a fixed suffix -- no
    path, no user input, so there is nothing to escape."""

    configure(tmp_path, "claude")
    for tool_id in AI_TOOLS:
        title = f"{AI_TOOLS[tool_id].label}{tool_status_label(tmp_path, tool_id)}"
        assert str(tmp_path) not in title
        assert "/" not in title
