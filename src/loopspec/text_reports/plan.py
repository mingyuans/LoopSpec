"""`loopspec plan validate|create|show|list|approve|archive|rollback`."""

from __future__ import annotations

from typing import Any

from .common import (
    Report,
    columns,
    fields,
    flow_lines,
    join,
    sanitize,
    section,
    spec_nodes,
    steps,
    value,
    warning_lines,
)

PROMPT_VALIDATED = (
    "The request compiled and satisfies the project constraints. This is read-only:\n"
    "nothing was saved or approved. digest identifies exactly this graph."
)
PROMPT_REVISION = (
    "A revision preview of the approved plan: nothing was saved. Show the human the\n"
    "new digest, addedInstances and rerunNodes, and only after they confirm run the\n"
    "command in NEXT STEPS."
)
PROMPT_CREATED = (
    "A draft plan was saved (replacedDraft says whether it replaced the previous\n"
    "draft). A draft never executes: show it with `loopspec plan show`, present it to\n"
    "a human and approve it with --digest only after they explicitly confirm."
)
PROMPT_SHOWN = (
    "One plan of this change. Present FLOW, NODES and digest to the human before\n"
    "asking for confirmation; `loopspec plan approve` needs exactly this digest."
)
PROMPT_FLOW = (
    "The Fragment instances of the plan in order: instance id, the Fragment it uses,\n"
    "its requires and, for instances that send failures back, on_fail."
)
PROMPT_NODES = (
    "Every compiled leaf node: what it writes (generates, or gate outputs for a\n"
    "gate), which instruction and template it reads (relative to the workflow\n"
    "home), what it requires, and how a gate failure is reworked (gate.on_fail)."
)
PROMPT_LIST = "Every plan of this change, oldest first, with status and revision."
PROMPT_APPROVED = (
    "The plan (or revision) is approved and executable. rerunNodes lists nodes a\n"
    "revision sends back to be done again."
)
PROMPT_ARCHIVED = "The plan was archived; its directory stays as it was."
PROMPT_ROLLBACK = (
    "A failed gate was reworked by its own on_fail: the outputs and reports of the\n"
    "nodes in reset were archived into .attempts (attempt number below). Business\n"
    "code was not reverted. Fix the problem and redo the reset nodes."
)
PROMPT_WARNINGS = "Problems that did not stop the command, for example a state.md append failure."


def _warnings(payload: dict) -> list[str]:
    if "warnings" not in payload:
        return []
    return section("=== WARNINGS ===", PROMPT_WARNINGS, warning_lines(payload["warnings"]))


def _spec(spec: dict) -> list[str]:
    flow = flow_lines(spec.get("flow", []))
    if spec.get("based_on"):
        flow = [f"based_on: {sanitize(spec['based_on'])}", *flow]
    extra = {k: v for k, v in spec.items() if k not in ("flow", "nodes", "based_on")}
    flow += [f"{sanitize(k)}: {value(v)}" for k, v in sorted(extra.items())]
    return [
        *section("=== FLOW ===", PROMPT_FLOW, flow),
        *section("=== NODES ===", PROMPT_NODES, spec_nodes(spec.get("nodes", []))),
    ]


PLAN_FIELDS = (
    "changeName",
    "plan",
    "mode",
    "status",
    "valid",
    "digest",
    "replacedDraft",
    "baseRevision",
    "revision",
    "addedInstances",
    "rerunNodes",
    "baseline",
    "repository",
    "message",
)


def render_compiled(payload: dict) -> str:
    """`plan validate` (plan or revision mode) and `plan create`."""
    if payload.get("mode") == "revision":
        title, prompt = "=== REVISION PREVIEW ===", PROMPT_REVISION
    elif "mode" in payload:
        title, prompt = "=== PLAN VALID ===", PROMPT_VALIDATED
    else:
        title, prompt = "=== DRAFT PLAN ===", PROMPT_CREATED
    rows = [(key, payload[key]) for key in PLAN_FIELDS if key in payload]
    lines = section(title, prompt, fields(rows))
    lines += _spec(payload["spec"])
    lines += _warnings(payload)
    lines += steps(payload.get("nextSteps", []))
    return join(lines)


META_FIELDS = (
    "status",
    "revision",
    "digest",
    "created",
    "approved_at",
    "note",
    "archived_at",
    "archive_note",
)


def render_show(payload: dict) -> str:
    meta: dict[str, Any] = payload["meta"]
    rows: list[tuple[str, Any]] = [
        ("changeName", payload["changeName"]),
        ("plan", payload["plan"]),
        ("active", payload["active"]),
    ]
    rows += [(f"meta.{key}", meta[key]) for key in META_FIELDS if key in meta]
    rows += [(f"meta.{k}", v) for k, v in sorted(meta.items()) if k not in (*META_FIELDS, "plan")]
    if meta.get("plan") != payload["plan"]:
        rows.append(("meta.plan", meta.get("plan")))
    rows += [(key, payload[key]) for key in ("baseline", "repository") if key in payload]
    return join([*section("=== PLAN ===", PROMPT_SHOWN, fields(rows)), *_spec(payload["spec"])])


def render_list(payload: dict) -> str:
    rows = [["plan", "status", "revision", "active", "details"]]
    for item in payload["plans"]:
        details = [
            f"{key}: {value(item[key])}"
            for key in ("created", "approvedAt", "archivedAt", "note", "archiveNote")
            if item.get(key) is not None
        ]
        known = ("plan", "status", "revision", "active", "created", "approvedAt", "archivedAt")
        details += [
            f"{k}: {value(v)}"
            for k, v in sorted(item.items())
            if k not in (*known, "note", "archiveNote")
        ]
        rows.append(
            [
                sanitize(item["plan"]),
                sanitize(item["status"]),
                value(item["revision"]),
                value(item["active"]),
                sanitize("; ".join(details)),
            ]
        )
    head = fields(
        [
            ("changeName", payload["changeName"]),
            ("baseline", payload["baseline"]),
            ("repository", payload["repository"]),
        ]
    )
    body = [*head, "", *(columns(rows) if payload["plans"] else ["(no plans yet)"])]
    return join(section("=== PLANS ===", PROMPT_LIST, body))


def _result(title: str, prompt: str, keys: tuple[str, ...], payload: dict) -> str:
    rows = [(key, payload[key]) for key in keys if key in payload]
    lines = section(title, prompt, fields(rows))
    lines += _warnings(payload)
    lines += steps(payload.get("nextSteps", []))
    return join(lines)


APPROVE_FIELDS = (
    "changeName",
    "plan",
    "status",
    "revision",
    "digest",
    "alreadyApproved",
    "rerunNodes",
)
ARCHIVE_FIELDS = ("changeName", "plan", "status", "archivedAt", "message")
ROLLBACK_FIELDS = ("changeName", "plan", "attempt", "gate", "reset", "message")


def render_approve(payload: dict) -> str:
    return _result("=== PLAN APPROVED ===", PROMPT_APPROVED, APPROVE_FIELDS, payload)


def render_archive(payload: dict) -> str:
    return _result("=== PLAN ARCHIVED ===", PROMPT_ARCHIVED, ARCHIVE_FIELDS, payload)


def render_rollback(payload: dict) -> str:
    return _result("=== ROLLBACK ===", PROMPT_ROLLBACK, ROLLBACK_FIELDS, payload)


COMPILED_KEYS = frozenset({*PLAN_FIELDS, "spec", "warnings", "nextSteps"})
VALIDATE = Report(render_compiled, COMPILED_KEYS)
CREATE = Report(render_compiled, COMPILED_KEYS)
SHOW = Report(
    render_show,
    frozenset({"changeName", "plan", "active", "meta", "spec", "baseline", "repository"}),
)
LIST = Report(render_list, frozenset({"changeName", "plans", "baseline", "repository"}))
APPROVE = Report(render_approve, frozenset({*APPROVE_FIELDS, "warnings", "nextSteps"}))
ARCHIVE = Report(render_archive, frozenset({*ARCHIVE_FIELDS, "warnings", "nextSteps"}))
ROLLBACK = Report(render_rollback, frozenset({*ROLLBACK_FIELDS, "warnings", "nextSteps"}))
