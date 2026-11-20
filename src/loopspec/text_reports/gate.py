"""`loopspec state add` and `loopspec gate begin|record`."""

from __future__ import annotations

from typing import Any

from .common import (
    Report,
    compact,
    fields,
    join,
    quote,
    sanitize,
    section,
    warning_lines,
)

PROMPT_STATE = (
    "The record was appended to the matching section of state.md (append only).\n"
    "line is the exact text written, quoted below."
)
PROMPT_BEGIN = (
    "A review round is open and the code under review is pinned (scopeDigest).\n"
    "Review or test exactly the paths below, write the report under artifacts/, then\n"
    "run `loopspec gate record` with this roundId. If the code changes during the\n"
    "review, run gate begin again. The round id is not a credential."
)
PROMPT_PATHS = (
    "The changed paths in this gate's evidence scope: kind of change and path, then\n"
    "the file as staged (index) and in the working tree (none: no file there)."
)
PROMPT_RECORD = (
    "The gate verdict was recorded as evidence (evidenceRecorded). On FAIL, follow\n"
    "`loopspec change status`: the gate's own on_fail decides the rework."
)
PROMPT_ASSURANCE = (
    "The system assurance check over the full delivery diff. verdict is the result\n"
    "(recorded says whether it was written; a blocked node lists blockedBy). Every\n"
    "gap category below must be empty for PASS: unknown_paths (no rule matches),\n"
    "missing_evidence and stale_evidence (no valid gate covers a path), missing_fragments\n"
    "(the plan lacks a Fragment a rule requires; revise the plan), diverged_commits\n"
    "(intermediate commits that are neither baseline nor reviewed content)."
)
PROMPT_CAPABILITIES = "Which capabilities each changed path needs, by the assurance rules."
PROMPT_WARNINGS = "Warnings that do not change the verdict; mention them in the report summary."


def render_state(payload: dict) -> str:
    keys = ("changeName", "scope", "plan", "section", "path")
    rows = [(key, payload[key]) for key in keys if key in payload]
    body = [*fields(rows), "line:", *quote(payload["line"])]
    lines = section("=== STATE RECORD ADDED ===", PROMPT_STATE, body)
    if "warnings" in payload:
        lines += section("=== WARNINGS ===", PROMPT_WARNINGS, warning_lines(payload["warnings"]))
    return join(lines)


def _blob(blob: Any) -> str:
    """`mode 100644, sha256 <hash>, <n> bytes`, or `none` when the side has no file."""
    if not isinstance(blob, dict):
        return compact(blob) if blob is not None else "none"
    parts = [f"{sanitize(k)} {compact(v)}" for k, v in blob.items() if k != "size"]
    if "size" in blob:
        parts.append(f"{compact(blob['size'])} bytes")
    return ", ".join(parts)


def render_begin(payload: dict) -> str:
    rows = [
        (key, payload[key]) for key in ("gate", "roundId", "scopeDigest", "baseline", "planDigest")
    ]
    body = [*fields(rows), "instruction:", *quote(payload["instruction"])]
    lines = section("=== GATE ROUND ===", PROMPT_BEGIN, body)
    review: list[str] = []
    for item in payload["paths"]:
        review.append(f"- {sanitize(item.get('kind'))} {sanitize(item.get('path'))}")
        for side in ("index", "worktree"):
            review.append(f"    {side}: {_blob(item.get(side))}")
        extra = {k: v for k, v in item.items() if k not in ("kind", "path", "index", "worktree")}
        review += [f"    {sanitize(k)}: {compact(v)}" for k, v in sorted(extra.items())]
    lines += section(
        "=== REVIEW INPUT ===", PROMPT_PATHS, review or ["(no changed paths in scope)"]
    )
    lines += section("=== WARNINGS ===", PROMPT_WARNINGS, warning_lines(payload["warnings"]))
    return join(lines)


GAPS = (
    "unknown_paths",
    "missing_evidence",
    "stale_evidence",
    "missing_fragments",
    "diverged_commits",
)


def _assurance(payload: dict) -> list[str]:
    rows: list[tuple[str, Any]] = [
        (key, payload[key])
        for key in ("gate", "verdict", "passed", "recorded", "blockedBy", "diffDigest", "baseline")
        if key in payload
    ]
    body = fields(rows)
    for gap in GAPS:
        items = payload.get(gap) or []
        body += ["", f"{gap}:"]
        body += [f"  - {compact(item)}" for item in items] or ["  (none)"]
    lines = section("=== ASSURANCE ===", PROMPT_ASSURANCE, body)
    required = payload.get("requiredCapabilities") or {}
    caps = [f"- {sanitize(path)}: {compact(needs)}" for path, needs in sorted(required.items())]
    lines += section("=== REQUIRED CAPABILITIES ===", PROMPT_CAPABILITIES, caps or ["(none)"])
    lines += section("=== WARNINGS ===", PROMPT_WARNINGS, warning_lines(payload.get("warnings")))
    return lines


def render_record(payload: dict) -> str:
    if "evidenceRecorded" not in payload:
        return join(_assurance(payload))
    rows = [(key, payload[key]) for key in ("gate", "verdict", "roundId", "evidenceRecorded")]
    lines = section("=== GATE RECORDED ===", PROMPT_RECORD, fields(rows))
    lines += section("=== WARNINGS ===", PROMPT_WARNINGS, warning_lines(payload["warnings"]))
    return join(lines)


STATE_ADD = Report(
    render_state,
    frozenset({"changeName", "scope", "plan", "section", "path", "line", "warnings"}),
)
BEGIN = Report(
    render_begin,
    frozenset(
        {
            "gate",
            "roundId",
            "scopeDigest",
            "baseline",
            "planDigest",
            "paths",
            "warnings",
            "instruction",
        }
    ),
)
RECORD = Report(
    render_record,
    frozenset(
        {
            "gate",
            "verdict",
            "roundId",
            "evidenceRecorded",
            "warnings",
            "passed",
            "recorded",
            "blockedBy",
            "diffDigest",
            "baseline",
            "requiredCapabilities",
            *GAPS,
        }
    ),
)
