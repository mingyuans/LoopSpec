"""Parsing and interactive selection for `loopspec init --tools`.

`questionary` is imported at module scope but only *called* from `pick_tools()`,
which `init` reaches solely after confirming it has a real terminal and is not
emitting JSON (design D3). The import itself touches no terminal.

Candidate text passed to the picker is registry constants only -- display names
and a fixed status suffix. `questionary` renders straight to the terminal and
never passes through `presentation.Presenter`, so that module's escaping
guarantee does not extend here; the safety comes from there being nothing
user-controlled to escape (design D8).
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import questionary

from .errors import ConfigValidationError
from .scaffold import tool_is_configured
from .tool_registry import AI_TOOLS


def resolve_tools_arg(raw: str | None) -> list[str]:
    """Resolve `--tools` into a concrete, de-duplicated list of tool ids.

    Returns `[]` for `"none"` or when `raw` is `None` (the caller decides
    whether `None` should instead trigger an interactive prompt).
    """

    if raw is None:
        return []

    normalized = raw.strip().lower()
    if normalized == "none":
        return []
    if normalized == "all":
        return sorted(AI_TOOLS)

    requested = [part.strip().lower() for part in raw.split(",") if part.strip()]
    unknown = [tool_id for tool_id in requested if tool_id not in AI_TOOLS]
    if unknown:
        raise ConfigValidationError(
            f"Unknown tool id(s): {', '.join(unknown)}",
            fix=f"Valid tool ids: {', '.join(sorted(AI_TOOLS))}",
        )

    selected: list[str] = []
    for tool_id in requested:
        if tool_id not in selected:
            selected.append(tool_id)
    return selected


def is_interactive() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


def tool_is_detected(project_path: Path, tool_id: str) -> bool:
    """Whether this project looks like it uses this tool, configured or not.

    Deliberately *not* in `scaffold.py`: detection only drives presentation and
    pre-selection, and must never leak into the created/refreshed split, which
    answers to `tool_is_configured()` alone (design D4).
    """

    tool = AI_TOOLS[tool_id]
    if tool.detection_paths is not None:
        return any((project_path / candidate).exists() for candidate in tool.detection_paths)
    return (project_path / tool.skills_dir).is_dir()


def tool_status_label(project_path: Path | None, tool_id: str) -> str:
    """Suffix telling the user whether picking this tool creates or overwrites.

    Reuses the same "are its skill files on disk" test as the scaffolder, so
    there is only one notion of "configured" -- and still no state file.
    Detection likewise goes through `tool_is_detected()`, so there is exactly
    one place that decides what "detected" means.
    """

    if project_path is None:
        return ""
    if tool_is_configured(project_path, tool_id):
        return " (configured)"
    if tool_is_detected(project_path, tool_id):
        return " (detected)"
    return ""


def _echo_selection(
    project_path: Path | None, selected: list[str], print_fn: Callable[[str], None]
) -> None:
    """Spell out which picks overwrite existing files before anything is written."""

    if project_path is None or not selected:
        return
    parts = [
        f"{tool_id} (refresh)" if tool_is_configured(project_path, tool_id) else tool_id
        for tool_id in selected
    ]
    print_fn(f"Selected: {', '.join(parts)}")


PICKER_INSTRUCTION = "↑↓ navigate • Space toggle • type to filter • Enter confirm"
INTERRUPT_NOTICE = "No tools configured. Re-run `loopspec init` to pick some."


def _preselected(project_path: Path | None) -> tuple[set[str], list[str]]:
    """Which tools start checked, and which of them were pre-selected by detection.

    First-time setup (nothing configured yet) starts from what is detected on
    disk. Every later run starts from what is *configured*, so re-running `init`
    defaults to refreshing the tools already set up rather than quietly widening
    the scope to whatever editors have since been installed (design D5).
    """

    if project_path is None:
        return set(), []

    configured = {tool_id for tool_id in AI_TOOLS if tool_is_configured(project_path, tool_id)}
    if configured:
        return configured, []

    detected = [tool_id for tool_id in AI_TOOLS if tool_is_detected(project_path, tool_id)]
    return set(detected), detected


def pick_tools(
    project_path: Path | None = None,
    *,
    # `input` shadows the builtin, deliberately: these two are forwarded verbatim
    # to questionary and keeping its names makes the pass-through obvious.
    input: Any = None,
    output: Any = None,
    print_fn: Callable[[str], None] = print,
) -> list[str]:
    """Searchable multi-select over the tool registry; returns chosen tool ids.

    `input`/`output` are passed straight through to `questionary`, which is what
    makes this testable without a terminal: a `create_pipe_input()` plus a
    `DummyOutput()` drive it from a byte string of keypresses (design D2).

    Ctrl+C means "configure nothing this run" rather than an exception: `init`
    has already created the workflow home by this point, and letting the
    traceback escape would leave that behind with no explanation (design D9).
    """

    checked, detected_preselection = _preselected(project_path)

    if detected_preselection:
        names = ", ".join(AI_TOOLS[tool_id].label for tool_id in detected_preselection)
        print_fn(f"Detected tool directories: {names} (pre-selected for first-time setup)")

    choices = [
        questionary.Choice(
            title=f"{AI_TOOLS[tool_id].label}{tool_status_label(project_path, tool_id)}",
            value=tool_id,
            checked=tool_id in checked,
        )
        for tool_id in AI_TOOLS
    ]

    try:
        answer = questionary.checkbox(
            f"Select tools to set up ({len(AI_TOOLS)} available)",
            choices=choices,
            instruction=PICKER_INSTRUCTION,
            use_arrow_keys=True,
            # j/k would be swallowed as navigation before reaching the filter.
            use_jk_keys=False,
            use_search_filter=True,
            input=input,
            output=output,
        ).unsafe_ask()
    except KeyboardInterrupt:
        print_fn(INTERRUPT_NOTICE)
        return []

    if not answer:
        return []

    # Registry order, de-duplicated -- questionary preserves choice order, but
    # the caller's contract does not depend on that.
    selected = [tool_id for tool_id in AI_TOOLS if tool_id in set(answer)]
    _echo_selection(project_path, selected, print_fn)
    return selected


def prompt_tools_interactively(
    project_path: Path | None = None,
    input_fn: Callable[[str], str] = input,
    print_fn: Callable[[str], None] = print,
) -> list[str]:
    """Print a numbered tool list and parse the user's comma-separated reply.

    Kept as a fallback for callers that cannot run the full picker (and for the
    tests that pin its behaviour); `init` prefers `pick_tools()`.
    """

    ids = sorted(AI_TOOLS)
    print_fn("Which AI tools should loopspec scaffold skills/commands for?")
    for index, tool_id in enumerate(ids, start=1):
        print_fn(f"  {index}) {tool_id}{tool_status_label(project_path, tool_id)}")
    print_fn("Enter comma-separated numbers, 'all', or 'none':")
    reply = input_fn("> ").strip().lower()

    if reply in ("", "none"):
        return []
    if reply == "all":
        _echo_selection(project_path, ids, print_fn)
        return ids

    selected: list[str] = []
    for token in reply.split(","):
        token = token.strip()
        if not token:
            continue
        if not token.isdigit() or not (1 <= int(token) <= len(ids)):
            raise ConfigValidationError(
                f"Invalid selection: {token}",
                fix=f"Enter a number between 1 and {len(ids)}, 'all', or 'none'.",
            )
        tool_id = ids[int(token) - 1]
        if tool_id not in selected:
            selected.append(tool_id)
    _echo_selection(project_path, selected, print_fn)
    return selected
