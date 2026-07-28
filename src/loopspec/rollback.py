"""Reset closure computation and rollback execution."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import yaml

from .errors import NoFailedGateError, RetriesExhaustedError
from .gate_outcome import GateOutcome
from .graph import WorkflowGraph
from .outputs import node_output_patterns, resolve_outputs
from .state import compute_states, count_rollbacks


@dataclass
class RollbackResult:
    round: int
    gate: str
    closure: list[str]
    archived: list[str]
    archive_dir: Path
    rollbacks_used: int
    max_retries: int


def compute_reset_closure(graph: WorkflowGraph, gate_id: str) -> list[str]:
    """Reset closure = transitive successors of ({declared reset starts} ∪ {gate itself})."""

    gate_node = graph.node(gate_id)
    assert gate_node.gate is not None

    seed = set(gate_node.gate.on_fail.reset) | {gate_id}
    closure: set[str] = set()
    stack = list(seed)
    while stack:
        current = stack.pop()
        if current in closure:
            continue
        closure.add(current)
        stack.extend(graph.dependents(current))

    order = graph.build_order()
    return [node_id for node_id in order if node_id in closure]


def _next_round_number(change_dir: Path) -> int:
    attempts_dir = change_dir / ".attempts"
    if not attempts_dir.is_dir():
        return 1
    existing = [
        int(path.name.split("-", 1)[1])
        for path in attempts_dir.glob("round-*")
        if path.is_dir() and path.name.split("-", 1)[1].isdigit()
    ]
    return max(existing, default=0) + 1


def _cleanup_empty_dirs(artifact_dir: Path, exclude: set[Path]) -> None:
    candidates = sorted(
        (p for p in artifact_dir.rglob("*") if p.is_dir()),
        key=lambda p: len(p.parts),
        reverse=True,
    )
    for path in candidates:
        if path in exclude or any(excluded in path.parents for excluded in exclude):
            continue
        try:
            next(path.iterdir())
        except StopIteration:
            path.rmdir()
        except FileNotFoundError:
            continue


def execute_rollback(
    graph: WorkflowGraph,
    change_dir: Path,
    artifact_dir: Path,
    gate_id: str,
    outcome: GateOutcome,
) -> RollbackResult:
    """Archive the reset closure's outputs to `.attempts/round-NNN/` and record metadata."""

    node = graph.node(gate_id)
    assert node.gate is not None

    closure = compute_reset_closure(graph, gate_id)
    round_no = _next_round_number(change_dir)
    round_dir = change_dir / ".attempts" / f"round-{round_no:03d}"
    round_dir.mkdir(parents=True, exist_ok=False)

    archived: list[str] = []
    for node_id in closure:
        target_node = graph.node(node_id)
        for pattern in node_output_patterns(target_node):
            for src in resolve_outputs(artifact_dir, pattern):
                rel = src.relative_to(change_dir)
                dst = round_dir / rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(src), str(dst))
                archived.append(str(rel))

    _cleanup_empty_dirs(artifact_dir, exclude={(change_dir / ".attempts").resolve()})

    meta = {
        "round": round_no,
        "gate": gate_id,
        "verdict": outcome.status,
        "summary": outcome.summary,
        "blocking_issues": outcome.blocking_issues,
        "reset_declared": node.gate.on_fail.reset,
        "reset_closure": closure,
        "archived_files": archived,
        "archived_at": datetime.now(UTC).astimezone().isoformat(),
    }
    (round_dir / "_meta.yaml").write_text(
        yaml.safe_dump(meta, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )

    return RollbackResult(
        round=round_no,
        gate=gate_id,
        closure=closure,
        archived=archived,
        archive_dir=round_dir,
        rollbacks_used=count_rollbacks(change_dir, gate_id),
        max_retries=node.gate.on_fail.max_retries,
    )


def rollback_change(graph: WorkflowGraph, change_dir: Path, artifact_dir: Path) -> RollbackResult:
    """Find the change's current failed gate (if any) and roll it back.

    Raises NoFailedGateError if no gate is failed, or RetriesExhaustedError if the
    only actionable gate has already exhausted its retries.
    """

    states = compute_states(graph, change_dir, artifact_dir)
    for node_id in graph.build_order():
        state = states[node_id]
        if state.status == "failed":
            assert state.verdict is not None
            return execute_rollback(graph, change_dir, artifact_dir, node_id, state.verdict)

    for node_id in graph.build_order():
        if states[node_id].status == "exhausted":
            raise RetriesExhaustedError(
                f"Gate '{node_id}' has exhausted its retries and cannot be rolled back again.",
                fix=f"Run `loopspec history` to review past failures for '{node_id}', "
                "or escalate to a human.",
            )

    raise NoFailedGateError(
        "No gate is currently in a failed state; there is nothing to roll back.",
        fix="Run `loopspec status` to see the current state.",
    )
