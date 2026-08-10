"""Plain-text `loopspec status` report, written for an LLM to read.

The contract, which the tests pin down:

* **Plain text.** No ANSI escapes, no colour, no glyphs, no spinner, no Markdown
  syntax. Nothing here goes through a rich `Console`, so nothing soft-wraps to a
  terminal width and nothing interprets console markup.
* **Byte-stable.** The same payload renders to the same bytes regardless of
  terminal width, TTY-ness, or `NO_COLOR`. That is why this module exists
  separately from `presentation`, whose whole contract is the opposite (styled
  `Text` through a `Console`) -- see D1 in the change's design.
* **Single data path.** Everything rendered comes from the payload `cli.status`
  already built for `--json`. This module never touches the filesystem and never
  recomputes node state. Path *strings* are manipulated (absolute -> relative),
  which is not a second data path: no disk access, no state recomputation.

Sanitisation is the one structural defence this format has. `sanitize()` rewrites
control characters visibly, which kills newlines; because an interpolated value
cannot open a new line, it cannot forge a `=== SECTION ===` separator line. Once
the Markdown table was dropped there is no second line of defence left -- the
`|`-escaping rule went away with the table -- so this is not decoration and must
not be removed for readability.

Every interpolated value goes through `sanitize`, including the file paths a glob
node lists one per line. Those paths deserve a special mention: they used to be
collapsed into a count and never reached the report at all, so they are the
newest and by far the most numerous class of interpolated value here, and they
come straight off the filesystem.

`INDENT_CONTINUATION` guards a second, independent line of defence: a separator
line only reads as structure when it sits alone at the start of a line, and the
only interpolated value at column zero is a node id, which Pydantic pins to
kebab-case. Glob matches are not validated that way, so their continuation lines
are indented -- see `_node_lines`.
"""

from __future__ import annotations

from pathlib import PurePath, PurePosixPath
from typing import Any

from .outputs import is_glob
from .presentation import sanitize

# The one sanitisation entry point for both this report and `cli._fail`'s
# non-JSON branch. Re-exported rather than reimplemented: the two outputs share
# an origin (user-supplied change names, filesystem paths) and a destination (an
# LLM's context), so they must not drift into two standards. See D10.
__all__ = ["render_status_report", "render_error_report", "sanitize"]

SECTION_OVERVIEW = "=== OVERVIEW ==="
SECTION_NODES = "=== NODES ==="
SECTION_GATE_FAILURES = "=== GATE FAILURES ==="
SECTION_PENDING_ROLLBACK = "=== PENDING ROLLBACK ==="
SECTION_NEXT_STEPS = "=== NEXT STEPS ==="
SECTION_ERROR = "=== ERROR ==="

#: Sub-block separator inside GATE FAILURES: three dashes, to sit a level below
#: the three equals signs of a section. Not Markdown either.
GATE_BLOCK = "--- {gate_id} ---"

#: Stands in for a match that resolved outside the artifact root -- a symlink
#: pointing out of the change directory. A constant, never an interpolated
#: value, so it cannot carry anything from the filesystem. See D17.
OUTSIDE_ROOT = "<outside artifact root>"

#: Placeholder for an empty NEXT STEPS, which is always-present by design.
NO_NEXT_STEPS = "(nothing queued)"

# --------------------------------------------------------------------------- #
# Built-in section prompts
#
# Copied verbatim from the change's design.md (Rendered Examples). These
# sentences decide how an LLM reads the whole report, so they are a design
# artifact, not an implementation detail: do not reword them here. No `#`
# comment prefix -- a testable scenario asserts no line of the report starts
# with `#`, and that assertion is how "the report uses no Markdown" is checked.
# --------------------------------------------------------------------------- #

PROMPT_OVERVIEW = (
    "Where this change lives and whether it is finished. Paths here are absolute;\n"
    "paths in every other section are relative to the artifact root."
)

PROMPT_NODES = (
    "Every node of the workflow, in dependency order. Columns: node id, status,\n"
    "output path, then notes in parentheses. Statuses: done (output exists),\n"
    "ready (dependencies met, output not written yet), blocked (waiting on the\n"
    "nodes named in its notes), failed / exhausted (a gate rejected the work).\n"
    "Do not pick a node yourself -- act on the one named in NEXT STEPS. A path\n"
    "like dir/{a,b}.md means the node is a gate that writes exactly one of the\n"
    "two; get the real paths from `loopspec instructions`. A node whose output\n"
    "is a glob lists every file it currently matches, one per line, indented\n"
    "under its first line; a path still containing * means that glob has no\n"
    "matches yet. Notes describe the node, so they stay on its first line."
)

PROMPT_GATE_FAILURES = (
    "A gate rejected the work. Each block below names the gate, why it failed,\n"
    "and which nodes a rollback would reset. Fix the blocking issues in the\n"
    "nodes listed under `reset` -- rolling back archives their current outputs."
)

PROMPT_PENDING_ROLLBACK = (
    "A rollback is available and is the only way forward from this gate. Run the\n"
    "command below verbatim, then read the status report again."
)

PROMPT_NEXT_STEPS = (
    "What to do next. Run these in order; the first one is enough to make\n"
    "progress. Run them as written rather than composing your own."
)

PROMPT_ERROR = (
    "The command failed and made no changes. `error` is a stable machine-readable\n"
    "code; `fix` is a suggested next command. Fix the cause rather than retrying\n"
    "the same command unchanged."
)

# --------------------------------------------------------------------------- #
# Field coverage
#
# Declared so a test can assert these sets equal the keys `status` actually
# produces. Add a field to the payload without deciding how it appears here and
# that test fails, which is the point: the alternative is a report that silently
# drops information. See D2.
# --------------------------------------------------------------------------- #

TOP_LEVEL_FIELDS = frozenset(
    {
        "changeName",
        "schemaName",
        "artifactsDir",
        "schemaPath",
        "changeRoot",
        "artifactRoot",
        "statePath",
        "stateExists",
        "isComplete",
        "nodes",
        "pendingRollback",
        "nextSteps",
    }
)

#: Deliberately omitted from the report, with the reason:
#: * artifactsDir -- implied by changeRoot, which is printed in full.
#: * schemaPath   -- its only visible effect is artifactRoot differing from
#:                   changeRoot, and that is shown when it happens.
#: * statePath    -- `stateExists` is the actionable half; the path is
#:                   changeRoot/state.md, derivable from what is printed.
OMITTED_TOP_LEVEL_FIELDS = frozenset({"artifactsDir", "schemaPath", "statePath"})

NODE_FIELDS = frozenset(
    {
        "id",
        "status",
        "outputPath",
        "resolvedOutputPath",
        "existingOutputPaths",
        "taskProgress",
        "missingDeps",
        "gate",
    }
)

#: resolvedOutputPath is the absolute form of the same paths the report already
#: shows relative to the artifact root (D4: absolute roots once, relative rows).
OMITTED_NODE_FIELDS = frozenset({"resolvedOutputPath"})

COLUMN_GAP = "  "
_LABEL_WIDTH_OVERVIEW = 15
_LABEL_WIDTH_BLOCK = 11


def _label(text: str, value: object, width: int) -> str:
    return f"{(text + ':').ljust(width)}{sanitize(value)}".rstrip()


def _relative_output(absolute: str, artifact_root: str) -> str:
    """`absolute` as a path relative to `artifact_root`, or the escape placeholder.

    Pure string work on values already in the payload -- no filesystem access and
    no state recomputation, so D2 stands. The escape case is handled by an
    explicit check rather than by catching `relative_to`'s `ValueError`: a bare
    `except ValueError` here would also swallow genuine errors added later.

    `existingOutputPaths` comes from `resolve_outputs`, which calls `.resolve()`
    and therefore *follows symlinks*, while the `.attempts/`-and-reserved-name
    filter looks at the unresolved path. A symlink pointing out of the change
    directory is thus a legitimate match whose resolved path sits outside the
    artifact root. Printing it would leak where it pointed -- exactly what
    `resolve_output_entries` keeps a relative name around to avoid -- and
    printing a `../../..` form would leak the same thing in another notation, so
    it becomes a constant placeholder instead. See D17.
    """

    candidate = PurePath(absolute)
    root = PurePath(artifact_root)
    if not candidate.is_relative_to(root):
        return OUTSIDE_ROOT
    return candidate.relative_to(root).as_posix()


def _gate_compact_output(output_path: dict[str, Any]) -> str:
    """`dir/{pass,fail}.ext` for a gate that has not written either output yet.

    A display form, not a usable literal path: writing goes through
    `loopspec instructions`, which returns `resolvedOutputPath.pass`/`.fail`.
    Spelling both paths out in full would push the notes column ~11 characters
    further right on every row.

    The two outputs of every built-in gate share a directory and a suffix. When
    they don't -- which the design does not cover -- fall back to showing both
    paths rather than inventing a brace form that cannot represent them.
    """

    pass_path = PurePosixPath(str(output_path["pass"]))
    fail_path = PurePosixPath(str(output_path["fail"]))
    same_place = pass_path.parent == fail_path.parent and pass_path.suffix == fail_path.suffix
    if not same_place:
        return f"{pass_path.as_posix()} | {fail_path.as_posix()}"
    compact = f"{{{pass_path.stem},{fail_path.stem}}}{pass_path.suffix}"
    parent = pass_path.parent.as_posix()
    return compact if parent == "." else f"{parent}/{compact}"


def _node_outputs(node: dict[str, Any], artifact_root: str) -> list[str]:
    """Every output path to show for one node: first line first, then continuations."""

    output_path = node.get("outputPath")
    existing = [
        _relative_output(path, artifact_root) for path in node.get("existingOutputPaths", [])
    ]

    if isinstance(output_path, dict):
        # A gate: exactly one verdict file can exist (two is `gate_output_conflict`,
        # which fails before rendering), so show the real one once it is there.
        return existing[:1] or [_gate_compact_output(output_path)]

    pattern = str(output_path)
    if not is_glob(pattern):
        return [pattern]
    # A glob with no matches still gets a row, so "one first line per node" holds
    # as an anchor; the pattern itself (with its `*`) says why there is no path.
    return existing or [pattern]


def _node_note(node: dict[str, Any], output_count: int, is_glob_node: bool) -> str:
    """The parenthesised note for a node: first match wins, by fixed priority.

    Not mutually exclusive cases -- `apply` is routinely both `blocked` and
    `tracks`-declaring, so its payload carries `missingDeps` *and* `taskProgress`
    at once. `blocked` comes first because it decides whether the node can be
    acted on at all, which matters more to the next action than a progress count.
    """

    missing = node.get("missingDeps")
    if node.get("status") == "blocked" and missing:
        joined = ", ".join(sanitize(dep) for dep in missing)
        return f"(needs: {joined})"

    progress = node.get("taskProgress")
    if progress is not None:
        return f"(tasks: {sanitize(progress['complete'])}/{sanitize(progress['total'])})"

    if node.get("status") in ("failed", "exhausted"):
        return "(see GATE FAILURES)"

    if is_glob_node and output_count == 0:
        return "(no matches yet)"

    return ""


def _node_lines(nodes: list[dict[str, Any]], artifact_root: str) -> list[str]:
    rows = []
    for node in nodes:
        outputs = [sanitize(value) for value in _node_outputs(node, artifact_root)]
        glob_node = not isinstance(node.get("outputPath"), dict) and is_glob(
            str(node.get("outputPath"))
        )
        note = _node_note(node, len(node.get("existingOutputPaths", [])), glob_node)
        rows.append((sanitize(node["id"]), sanitize(node["status"]), outputs, note))

    id_width = max((len(row[0]) for row in rows), default=0)
    status_width = max((len(row[1]) for row in rows), default=0)
    # Only first-line outputs set the column width. A deeply nested continuation
    # path would otherwise shove every row's notes to the right, and a
    # continuation has no column after it to align with anyway.
    output_width = max((len(row[2][0]) for row in rows), default=0)
    continuation_indent = " " * (id_width + len(COLUMN_GAP) + status_width + len(COLUMN_GAP))

    lines = []
    for node_id, status, outputs, note in rows:
        first = (
            f"{node_id.ljust(id_width)}{COLUMN_GAP}"
            f"{status.ljust(status_width)}{COLUMN_GAP}"
            f"{outputs[0].ljust(output_width)}{COLUMN_GAP}{note}"
        )
        lines.append(first.rstrip())
        # Indented, never flush left: a continuation path is filesystem-derived
        # and unvalidated, so at column zero it would be the first externally
        # controlled value able to sit where a separator line is read. See D16.
        lines.extend(continuation_indent + path for path in outputs[1:])
    return lines


def _gate_failure_lines(nodes: list[dict[str, Any]]) -> list[str]:
    lines: list[str] = []
    for node in nodes:
        gate = node.get("gate")
        if gate is None:
            continue
        if lines:
            lines.append("")
        lines.append(GATE_BLOCK.format(gate_id=sanitize(node["id"])))
        lines.append(_label("verdict", gate["verdict"], _LABEL_WIDTH_BLOCK))
        lines.append(_label("summary", gate["summary"] or "(none)", _LABEL_WIDTH_BLOCK))
        lines.append(
            _label(
                "rollbacks",
                f"{sanitize(gate['rollbacksUsed'])} of {sanitize(gate['maxRetries'])} used",
                _LABEL_WIDTH_BLOCK,
            )
        )
        closure = ", ".join(sanitize(dep) for dep in gate["resetClosure"])
        lines.append(_label("reset", closure, _LABEL_WIDTH_BLOCK))
        issues = gate.get("blockingIssues") or []
        lines.append("blocking issues:")
        if not issues:
            lines.append("  (none listed)")
        for index, issue in enumerate(issues, start=1):
            # Indented as well as sanitised. The indent is the readability fix
            # D10 allows -- an indented line cannot equal `=== ... ===` -- and is
            # explicitly not a licence to skip sanitising these multi-line
            # fields, which are the likeliest place to hide a forged separator.
            lines.append(f"  {index}. {sanitize(issue)}")
    return lines


def _section(separator: str, prompt: str, body: list[str]) -> list[str]:
    return [separator, prompt, "", *body]


def render_status_report(payload: dict[str, Any]) -> str:
    """Render `loopspec status`'s payload as the plain-text report."""

    artifact_root = str(payload["artifactRoot"])
    change_root = str(payload["changeRoot"])

    overview = [
        _label("change", payload["changeName"], _LABEL_WIDTH_OVERVIEW),
        _label("schema", payload["schemaName"], _LABEL_WIDTH_OVERVIEW),
        _label("change root", change_root, _LABEL_WIDTH_OVERVIEW),
    ]
    if artifact_root != change_root:
        # Only when a schema's second-level `path` makes them differ; otherwise
        # it is the same string twice.
        overview.append(_label("artifact root", artifact_root, _LABEL_WIDTH_OVERVIEW))
    state_label = "present" if payload["stateExists"] else "missing"
    overview.append(_label("state.md", state_label, _LABEL_WIDTH_OVERVIEW))
    overview.append(
        _label("complete", "yes" if payload["isComplete"] else "no", _LABEL_WIDTH_OVERVIEW)
    )

    nodes = payload["nodes"]
    sections = _section(SECTION_OVERVIEW, PROMPT_OVERVIEW, overview)
    sections += [""]
    sections += _section(SECTION_NODES, PROMPT_NODES, _node_lines(nodes, artifact_root))

    gate_failures = _gate_failure_lines(nodes)
    if gate_failures:
        # Conditional on purpose: an empty section would make "all fine" and
        # "something failed but no detail" look alike.
        sections += ["", *_section(SECTION_GATE_FAILURES, PROMPT_GATE_FAILURES, gate_failures)]

    pending = payload.get("pendingRollback")
    if pending is not None:
        sections += [
            "",
            *_section(
                SECTION_PENDING_ROLLBACK,
                PROMPT_PENDING_ROLLBACK,
                [
                    _label("gate", pending["gate"], _LABEL_WIDTH_BLOCK),
                    _label(
                        "reset",
                        ", ".join(sanitize(dep) for dep in pending["closure"]),
                        _LABEL_WIDTH_BLOCK,
                    ),
                    _label("command", pending["command"], _LABEL_WIDTH_BLOCK),
                ],
            ),
        ]

    steps = payload["nextSteps"]
    step_lines = [f"{index}. {sanitize(step)}" for index, step in enumerate(steps, start=1)]
    sections += [
        "",
        *_section(SECTION_NEXT_STEPS, PROMPT_NEXT_STEPS, step_lines or [NO_NEXT_STEPS]),
    ]

    return "\n".join(sections)


def render_error_report(error: object, message: object, fix: object) -> str:
    """Render a command failure the same way the status report renders a section.

    Shares the sanitisation entry point with `render_status_report` for a
    concrete reason: `message` interpolates a change name that was never format
    checked (read commands only test that the directory exists), so a newline in
    it would otherwise print a line the caller controls -- and separator lines
    are exactly what an LLM reads as structure here. `click.echo` is no
    safeguard: outside a TTY it strips ANSI, not newlines or `\\r`.
    """

    body = [
        _label("error", error, _LABEL_WIDTH_BLOCK),
        _label("message", message, _LABEL_WIDTH_BLOCK),
        _label("fix", fix, _LABEL_WIDTH_BLOCK),
    ]
    return "\n".join(_section(SECTION_ERROR, PROMPT_ERROR, body))
