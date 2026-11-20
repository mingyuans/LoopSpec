"""`loopspec fragment list|show|validate` and `loopspec profile list|show|validate|save`."""

from __future__ import annotations

from typing import Any

from .common import (
    Report,
    bullet,
    compact,
    fields,
    flow_lines,
    join,
    sanitize,
    section,
    spec_nodes,
    sub,
)

PROMPT_FRAGMENTS = (
    "Every Fragment available to plans: a reusable piece of workflow (nodes with\n"
    "instructions, templates and gates). source is local (this workflow home) or\n"
    "registry (the locked registry snapshot, version in registry). Inspect one with\n"
    "`loopspec fragment show <name>`."
)
PROMPT_FRAGMENT = (
    "One Fragment definition. Node paths (generates, instruction, template) are\n"
    "relative to the Fragment's own directory."
)
PROMPT_FRAGMENT_NODES = "The nodes of this Fragment; use names another Fragment a node expands to."
PROMPT_VALID = "The definition is valid. buildOrder is the order its nodes compile in."
PROMPT_PROFILES = (
    "Every Profile: a reusable flow template to adopt or adapt when planning, never\n"
    "a mandatory process. Inspect one with `loopspec profile show <name>`."
)
PROMPT_PROFILE = (
    "One Profile. FLOW lists the Fragment instances it uses; guidance is advice for\n"
    "the planner, not a rule."
)
PROMPT_PROFILE_VALID = (
    "The Profile compiles. buildOrder lists the leaf nodes in order, instances every\n"
    "Fragment instance, onFail how each gate's failure is reworked."
)
PROMPT_SAVED = "The active plan's flow was saved as a new Profile (never overwrites)."

HEAD = ("name", "version", "description", "source", "registry")


def _head(item: dict, skip: tuple[str, ...]) -> list[tuple[str, Any]]:
    rows: list[tuple[str, Any]] = [(key, compact(item[key])) for key in HEAD if key in item]
    rows += [(sanitize(k), compact(v)) for k, v in sorted(item.items()) if k not in (*HEAD, *skip)]
    return rows


def _fragment_block(item: dict) -> list[str]:
    return [
        *fields(_head(item, ("nodes",))),
        "nodes:",
        *[f"  {line}" for line in spec_nodes(item.get("nodes", []))],
    ]


def render_fragment_list(payload: dict) -> str:
    body: list[str] = []
    for item in payload["fragments"]:
        if body:
            body.append("")
        body += [sub(item.get("name", "?")), *_fragment_block(item)]
    return join(section("=== FRAGMENTS ===", PROMPT_FRAGMENTS, body or ["(no fragments)"]))


def render_fragment_show(payload: dict) -> str:
    lines = section("=== FRAGMENT ===", PROMPT_FRAGMENT, fields(_head(payload, ("nodes",))))
    lines += section("=== NODES ===", PROMPT_FRAGMENT_NODES, spec_nodes(payload.get("nodes", [])))
    return join(lines)


def render_fragment_validate(payload: dict) -> str:
    body = [
        *fields([("valid", payload["valid"])]),
        "buildOrder:",
        *bullet(payload["buildOrder"], "  "),
    ]
    return join(section("=== FRAGMENT VALID ===", PROMPT_VALID, body))


def _profile_block(item: dict) -> list[str]:
    lines = [*fields(_head(item, ("flow", "guidance"))), "flow:"]
    lines += [f"  {line}" for line in flow_lines(item.get("flow", []))]
    lines += ["guidance:", *bullet(item.get("guidance", []), "  ")]
    return lines


def render_profile_list(payload: dict) -> str:
    body: list[str] = []
    for item in payload["profiles"]:
        if body:
            body.append("")
        body += [sub(item.get("name", "?")), *_profile_block(item)]
    return join(section("=== PROFILES ===", PROMPT_PROFILES, body or ["(no profiles)"]))


def render_profile_show(payload: dict) -> str:
    return join(section("=== PROFILE ===", PROMPT_PROFILE, _profile_block(payload)))


def render_profile_validate(payload: dict) -> str:
    body = fields([("valid", payload["valid"]), ("name", payload["name"])])
    body += ["buildOrder:", *bullet(payload["buildOrder"], "  ")]
    body += ["instances:", *bullet(payload["instances"], "  ")]
    body.append("onFail:")
    on_fail = payload.get("onFail") or {}
    body += [f"  - {sanitize(gate)}: {compact(policy)}" for gate, policy in on_fail.items()]
    if not on_fail:
        body.append("  (none)")
    return join(section("=== PROFILE VALID ===", PROMPT_PROFILE_VALID, body))


def render_profile_save(payload: dict) -> str:
    rows = [("saved", payload["saved"]), ("includesRuntimeState", payload["includesRuntimeState"])]
    return join(section("=== PROFILE SAVED ===", PROMPT_SAVED, fields(rows)))


FRAGMENT_LIST = Report(render_fragment_list, frozenset({"fragments"}))
FRAGMENT_SHOW = Report(
    render_fragment_show,
    frozenset({"name", "version", "description", "nodes", "source", "registry"}),
)
FRAGMENT_VALIDATE = Report(render_fragment_validate, frozenset({"valid", "buildOrder"}))
PROFILE_LIST = Report(render_profile_list, frozenset({"profiles"}))
PROFILE_SHOW = Report(
    render_profile_show,
    frozenset({"name", "version", "description", "flow", "guidance", "source", "registry"}),
)
PROFILE_VALIDATE = Report(
    render_profile_validate, frozenset({"valid", "name", "buildOrder", "instances", "onFail"})
)
PROFILE_SAVE = Report(render_profile_save, frozenset({"saved", "includesRuntimeState"}))
