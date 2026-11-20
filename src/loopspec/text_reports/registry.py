"""`loopspec registry update|apply`."""

from __future__ import annotations

from typing import Any

from .common import (
    Report,
    bullet,
    compact,
    fields,
    join,
    sanitize,
    section,
    steps,
    warning_lines,
)

PROMPT_UPDATE = (
    "What a registry update would change. Nothing was written: registry.lock.yaml\n"
    "changes only when `loopspec registry apply --plan <planId>` runs after a human\n"
    "confirmed this preview. upToDate: true means there is nothing to apply.\n"
    "sourceChanged: true means the registry url or path changed (previousRegistry is\n"
    "the old source); show both and confirm the switch separately."
)
PROMPT_DEFINITIONS = "Fragments and Profiles the update adds, modifies or deletes."
PROMPT_FILES = (
    "Every changed file: status, then the path. upstreamPath and basePath point at\n"
    "the new and old snapshot copies for a side-by-side review."
)
PROMPT_CONFLICTS = (
    "Local definitions with the same name as a registry definition. They must be\n"
    "removed from the workflow home before apply."
)
PROMPT_BROKEN = "Changes whose plans reference a definition this update deletes."
PROMPT_WARNINGS = "Warnings to show the human with the preview."
PROMPT_APPLIED = (
    "The confirmed plan was applied: registry.lock.yaml (lock) now pins upstreamCommit."
)

UPDATE_FIELDS = (
    "upToDate",
    "planId",
    "baseCommit",
    "baseTag",
    "upstreamCommit",
    "upstreamTag",
    "baseAvailable",
    "migration",
    "sourceChanged",
)


def render_update(payload: dict) -> str:
    rows: list[tuple[str, Any]] = [("registry", compact(payload["registry"]))]
    rows += [(key, payload[key]) for key in UPDATE_FIELDS if key in payload]
    rows.append(("previousRegistry", compact(payload.get("previousRegistry"))))
    lines = section("=== REGISTRY UPDATE ===", PROMPT_UPDATE, fields(rows))
    definitions = [
        "- " + " ".join(sanitize(item.get(key)) for key in ("change", "kind", "name"))
        for item in payload["definitions"]
    ]
    lines += section("=== DEFINITIONS ===", PROMPT_DEFINITIONS, definitions or ["(none)"])
    files: list[str] = []
    for item in payload["files"]:
        files.append(f"- {sanitize(item.get('status'))} {sanitize(item.get('path'))}")
        files += [
            f"    {sanitize(k)}: {compact(v)}"
            for k, v in item.items()
            if k not in ("status", "path")
        ]
    lines += section("=== FILES ===", PROMPT_FILES, files or ["(none)"])
    lines += section("=== LOCAL CONFLICTS ===", PROMPT_CONFLICTS, bullet(payload["localConflicts"]))
    broken = [f"- {compact(item)}" for item in payload["brokenReferences"]]
    lines += section("=== BROKEN REFERENCES ===", PROMPT_BROKEN, broken or ["(none)"])
    lines += section("=== WARNINGS ===", PROMPT_WARNINGS, warning_lines(payload["warnings"]))
    lines += steps(payload["nextSteps"])
    return join(lines)


APPLY_FIELDS = ("applied", "lock", "upstreamCommit", "upstreamTag", "migration")


def render_apply(payload: dict) -> str:
    rows = [(key, payload[key]) for key in APPLY_FIELDS if key in payload]
    body = fields(rows)
    for key in ("added", "modified", "deleted"):
        body += [f"{key}:", *bullet(payload.get(key, []), "  ")]
    lines = section("=== REGISTRY APPLIED ===", PROMPT_APPLIED, body)
    lines += steps(payload.get("nextSteps", []))
    return join(lines)


UPDATE = Report(
    render_update,
    frozenset(
        {
            "registry",
            *UPDATE_FIELDS,
            "previousRegistry",
            "definitions",
            "files",
            "localConflicts",
            "brokenReferences",
            "warnings",
            "nextSteps",
        }
    ),
)
APPLY = Report(
    render_apply, frozenset({*APPLY_FIELDS, "added", "modified", "deleted", "nextSteps"})
)
