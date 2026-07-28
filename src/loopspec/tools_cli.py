"""Parsing and interactive selection for `loopspec init --tools`."""

from __future__ import annotations

import sys
from collections.abc import Callable

from .errors import ConfigValidationError
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


def prompt_tools_interactively(
    input_fn: Callable[[str], str] = input,
    print_fn: Callable[[str], None] = print,
) -> list[str]:
    """Print a numbered tool list and parse the user's comma-separated reply."""

    ids = sorted(AI_TOOLS)
    print_fn("Which AI tools should loopspec scaffold skills/commands for?")
    for index, tool_id in enumerate(ids, start=1):
        print_fn(f"  {index}) {tool_id}")
    print_fn("Enter comma-separated numbers, 'all', or 'none':")
    reply = input_fn("> ").strip().lower()

    if reply in ("", "none"):
        return []
    if reply == "all":
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
    return selected
