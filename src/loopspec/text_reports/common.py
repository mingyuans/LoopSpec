"""Pieces several command reports share: warnings, nodes, flows, memory indexes."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from ..text_format import (
    QUOTE,
    bullet,
    columns,
    fields,
    join,
    quote,
    quote_block,
    sanitize,
    section,
    steps,
    sub,
    value,
)

__all__ = [
    "QUOTE",
    "Report",
    "bullet",
    "columns",
    "fields",
    "flow_lines",
    "item_fields",
    "join",
    "memory_topics",
    "node_entry",
    "output_text",
    "quote",
    "quote_block",
    "compact",
    "sanitize",
    "section",
    "spec_nodes",
    "steps",
    "sub",
    "value",
    "warning_lines",
]


@dataclass(frozen=True)
class Report:
    """A hand-written text renderer and the payload keys it accounts for.

    `keys` lists every top-level key the renderer shows, optional ones included;
    `omitted` lists keys deliberately left out. Tests fail on any other key, so a
    new payload field must be rendered or consciously omitted.
    """

    render: Callable[[dict], str]
    keys: frozenset[str]
    omitted: frozenset[str] = frozenset()


def compact(item: Any) -> str:
    """One-line spelling of a nested value: dicts as `key=value; ...`."""
    if isinstance(item, dict):
        return "; ".join(f"{sanitize(k)}={compact(v)}" for k, v in item.items()) or "{}"
    if isinstance(item, list | tuple):
        return ", ".join(compact(v) for v in item) if item else "[]"
    return value(item)


def item_fields(
    item: dict, order: tuple[str, ...] = (), skip: tuple[str, ...] = (), indent: str = ""
) -> list[str]:
    """Fields of one list item: the known keys in `order`, then any other key, none dropped."""
    keys = [k for k in order if k in item] + sorted(k for k in item if k not in order)
    rows = [(sanitize(k), compact(item[k])) for k in keys if k not in skip]
    return fields(rows, indent=indent)


def warning_lines(warnings: Any) -> list[str]:
    """`warnings` is null, a list of strings, or a dict of path lists and totals."""
    if not warnings:
        return ["(none)"]
    if isinstance(warnings, dict):
        return fields([(sanitize(k), compact(v)) for k, v in warnings.items()])
    return bullet(warnings)


def output_text(output: Any) -> str:
    if isinstance(output, dict):
        return f"pass: {sanitize(output.get('pass'))} | fail: {sanitize(output.get('fail'))}"
    return value(output)


NODE_ORDER = (
    "id",
    "fragment",
    "status",
    "outputPath",
    "resolvedOutputPath",
    "existingOutputPaths",
    "missingDeps",
    "taskProgress",
    "gate",
    "reason",
)


def node_entry(entry: dict, indent: str = "") -> list[str]:
    """A node as `change status` sees it (id, status, output paths, gate state)."""
    return fields(node_rows(entry), indent=indent)


def node_rows(entry: dict) -> list[tuple[str, Any]]:
    rows: list[tuple[str, Any]] = []
    for key in NODE_ORDER:
        if key not in entry:
            continue
        item = entry[key]
        if key in ("outputPath", "resolvedOutputPath"):
            rows.append((key, output_text(item)))
        elif key == "taskProgress":
            rows.append(
                (
                    key,
                    f"{item['completed']} of {item['total']} done, {item['remaining']} remaining",
                )
            )
        elif isinstance(item, dict):
            rows.append((key, compact(item)))
        else:
            rows.append((key, value(item)))
    rows.extend((sanitize(k), compact(v)) for k, v in sorted(entry.items()) if k not in NODE_ORDER)
    return rows


def _on_fail(policy: dict | None) -> str:
    if not policy:
        return ""
    return f"on_fail: reset {', '.join(policy['reset'])}; max_retries {policy['max_retries']}"


def flow_lines(flow: list[dict]) -> list[str]:
    """One row per Fragment instance: id, the Fragment it uses, requires, on_fail."""
    rows = []
    for ref in flow:
        notes = []
        if ref.get("requires"):
            notes.append("requires: " + ", ".join(ref["requires"]))
        if ref.get("on_fail"):
            notes.append(_on_fail(ref["on_fail"]))
        extra = {k: v for k, v in ref.items() if k not in ("id", "use", "requires", "on_fail")}
        notes.extend(f"{k}: {compact(v)}" for k, v in sorted(extra.items()))
        rows.append(
            [sanitize(ref["id"]), f"use {sanitize(ref['use'])}", sanitize("; ".join(notes))]
        )
    return columns(rows) or ["(empty)"]


SPEC_NODE_ORDER = (
    "fragment",
    "description",
    "requires",
    "generates",
    "instruction",
    "template",
    "tracks",
)


def spec_nodes(nodes: list[dict]) -> list[str]:
    """Every compiled leaf node as a sub-block: what it writes, reads and gates on."""
    lines: list[str] = []
    for node in nodes:
        if lines:
            lines.append("")
        lines.append(sub(node["id"]))
        rows: list[tuple[str, Any]] = []
        for key in SPEC_NODE_ORDER:
            if key in node and node[key] not in (None, ""):
                rows.append((key, value(node[key]) if key == "requires" else node[key]))
        gate = node.get("gate")
        if gate:
            outputs = gate.get("outputs") or {}
            rows.append(("gate.outputs", output_text(outputs)))
            if gate.get("templates"):
                rows.append(("gate.templates", output_text(gate["templates"])))
            if gate.get("evidence"):
                evidence = gate["evidence"]
                rows.append(("gate.evidence.provides", value(evidence.get("provides", []))))
                rows.append(("gate.evidence.paths", value(evidence.get("paths", []))))
            if gate.get("assurance"):
                rows.append(("gate.assurance", gate["assurance"]))
            if gate.get("on_fail"):
                rows.append(("gate.on_fail", _on_fail(gate["on_fail"]).removeprefix("on_fail: ")))
            known = ("outputs", "templates", "evidence", "assurance", "on_fail")
            rows.extend(
                (f"gate.{k}", compact(v)) for k, v in sorted(gate.items()) if k not in known
            )
        known_node = ("id", "gate", *SPEC_NODE_ORDER)
        rows.extend(
            (sanitize(k), compact(v))
            for k, v in sorted(node.items())
            if k not in known_node and v is not None
        )
        lines.extend(fields(rows))
    return lines or ["(no nodes)"]


def memory_topics(topics: list[dict], indent: str = "") -> list[str]:
    """`- <topic>: <title>` with path, size, status and hint on the lines below."""
    lines = []
    for topic in topics:
        lines.append(f"{indent}- {sanitize(topic.get('topic'))}: {sanitize(topic.get('title'))}")
        detail = (
            f"{sanitize(topic.get('path'))} ({value(topic.get('bytes'))} bytes,"
            f" status {sanitize(topic.get('status'))})"
        )
        lines.append(f"{indent}  path: {detail}")
        if topic.get("hint"):
            lines.append(f"{indent}  hint: {sanitize(topic['hint'])}")
        extra = {
            k: v
            for k, v in topic.items()
            if k not in ("topic", "title", "path", "bytes", "status", "hint")
        }
        lines.extend(f"{indent}  {sanitize(k)}: {compact(v)}" for k, v in sorted(extra.items()))
    return lines or [f"{indent}(no topics)"]
