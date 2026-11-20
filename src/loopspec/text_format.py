"""Plain-text building blocks shared by every LLM-facing command report.

The contract (see `status_report` for its origin):

* Plain text only: no ANSI, no colour, no Markdown headings. Sections are
  `=== TITLE ===` lines at column zero followed by a prompt paragraph; sub-blocks
  are `--- title ---` lines.
* Column zero only ever holds constant titles and labels, numbered next steps
  built from CLI-generated commands, or validated ids (change names, plan and
  node ids). Every other value goes through `sanitize` (one line, control
  characters made visible) or `quote` (every line indented by four spaces), so
  untrusted text can never open a section, a sub-block or a step of its own.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

from .presentation import escape_control, sanitize

__all__ = [
    "NO_NEXT_STEPS",
    "QUOTE",
    "bullet",
    "columns",
    "fields",
    "flag",
    "quote",
    "quote_block",
    "sanitize",
    "section",
    "steps",
    "sub",
]

QUOTE = "    "
NO_NEXT_STEPS = "(nothing queued)"
NONE = "(none)"
# Everything sanitize() escapes except \n and \t, which quoted text keeps.
_QUOTED_CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f-\x9f  ]")

PROMPT_NEXT_STEPS = (
    "What to do next. Run these in order; the first one is enough to make progress.\n"
    "Run them as written rather than composing your own."
)


def section(header: str, prompt: str, body: list[str]) -> list[str]:
    return [header, prompt, "", *body, ""]


def sub(title: str) -> str:
    """A `--- title ---` sub-block header; the title is sanitized."""
    return f"--- {sanitize(title)} ---"


def value(item: Any) -> str:
    """JSON-like scalar spelling: true/false/null stay recognisable, the rest is sanitized."""
    if item is True:
        return "true"
    if item is False:
        return "false"
    if item is None:
        return "null"
    if isinstance(item, list | tuple):
        return ", ".join(value(x) for x in item) if item else "[]"
    return sanitize(item)


def fields(rows: list[tuple[str, Any]], width: int = 0, indent: str = "") -> list[str]:
    if not rows:
        return []
    rows = [(sanitize(label), item) for label, item in rows]
    width = max(width, max(len(label) for label, _ in rows) + 2)
    return [f"{indent}{label + ':':<{width}}{value(item)}" for label, item in rows]


def columns(rows: list[list[str]], indent: str = "") -> list[str]:
    if not rows:
        return []
    widths = [max(len(row[i]) for row in rows) for i in range(len(rows[0]) - 1)]
    return [
        indent
        + "  ".join(
            [*(cell.ljust(width) for cell, width in zip(row, widths, strict=False)), row[-1]]
        ).rstrip()
        for row in rows
    ]


def quote(content: str, indent: str = QUOTE) -> list[str]:
    text = content.replace("\r\n", "\n").replace("\r", "\n")
    text = _QUOTED_CONTROL.sub(lambda match: escape_control(match.group()), text)
    return [indent + line for line in text.removesuffix("\n").split("\n")]


def quote_block(label: str, content: str, detail: str = "", end: str | None = None) -> list[str]:
    """A bounded quote: `--- begin <label> (N lines) ---`, N indented lines, `--- end <end> ---`.

    The begin and end lines are written only here; the quoted lines are all indented,
    so text inside the block can never end it early or open a section of its own.
    """
    body = quote(content) if content else []
    count = f"{len(body)} line" + ("" if len(body) == 1 else "s")
    extra = f", {detail}" if detail else ""
    return [
        f"--- begin {sanitize(label)} ({count}{extra}) ---",
        *body,
        f"--- end {sanitize(end if end is not None else label)} ---",
    ]


def bullet(items: Iterable[Any], indent: str = "", empty: str = NONE) -> list[str]:
    lines = [f"{indent}- {value(item)}" for item in items]
    return lines or [f"{indent}{empty}"]


def flag(item: Any) -> str:
    return value(bool(item))


def steps(next_steps: list[str], prompt: str = PROMPT_NEXT_STEPS) -> list[str]:
    body = [f"{index}. {sanitize(step)}" for index, step in enumerate(next_steps, 1)]
    return section("=== NEXT STEPS ===", prompt, body or [NO_NEXT_STEPS])


def join(lines: list[str]) -> str:
    while lines and lines[-1] == "":
        lines = lines[:-1]
    return "\n".join(lines) + "\n"
