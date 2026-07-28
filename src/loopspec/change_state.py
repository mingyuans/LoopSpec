"""state.md creation and reading (change-level LLM working memory)."""

from __future__ import annotations

from pathlib import Path

STATE_TEMPLATE = """# Change State

## Current Focus
- Pending first node.

## Frozen Decisions
- None yet.

## Decision Log
- None yet.

## Rejected Options
- None yet.

## Open Questions
- None yet.

## Artifact Notes
- None yet.
"""


def state_path(change_dir: Path) -> Path:
    return change_dir / "state.md"


def create_initial_state(change_dir: Path) -> Path:
    path = state_path(change_dir)
    path.write_text(STATE_TEMPLATE, encoding="utf-8")
    return path


def read_state_for_instruction(change_dir: Path) -> tuple[str | None, list[str]]:
    """Return (state text, warnings). Missing state.md is not an error."""

    path = state_path(change_dir)
    if not path.is_file():
        return None, ["state_missing"]
    return path.read_text(encoding="utf-8"), []
