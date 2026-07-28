"""Node state derivation (the core five-state machine)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .gate_outcome import GateOutcome, read_gate_outcome
from .graph import WorkflowGraph
from .outputs import outputs_exist


@dataclass
class NodeState:
    id: str
    status: str  # blocked | ready | done | failed | exhausted
    missing_deps: list[str] = field(default_factory=list)
    verdict: GateOutcome | None = None
    rollbacks_used: int = 0
    max_retries: int = 0


def count_rollbacks(change_dir: Path, gate_id: str) -> int:
    """Count completed rollback rounds recorded against `gate_id`."""

    attempts_dir = change_dir / ".attempts"
    if not attempts_dir.is_dir():
        return 0
    count = 0
    for round_dir in sorted(attempts_dir.glob("round-*")):
        meta_path = round_dir / "_meta.yaml"
        if not meta_path.is_file():
            continue
        meta = yaml.safe_load(meta_path.read_text(encoding="utf-8")) or {}
        if meta.get("gate") == gate_id:
            count += 1
    return count


def compute_states(
    graph: WorkflowGraph, change_dir: Path, artifact_dir: Path
) -> dict[str, NodeState]:
    """Two-pass derivation: first the `completed` set, then each node's outward status."""

    completed: set[str] = set()
    outcomes: dict[str, GateOutcome] = {}

    for node_id in graph.build_order():
        node = graph.node(node_id)
        if node.gate is None:
            assert node.generates is not None
            if outputs_exist(artifact_dir, node.generates):
                completed.add(node_id)
            continue

        outcome = read_gate_outcome(artifact_dir, node.gate.outputs)
        if outcome is None:
            continue
        outcomes[node_id] = outcome
        if outcome.passed:
            completed.add(node_id)

    states: dict[str, NodeState] = {}
    for node_id in graph.build_order():
        node = graph.node(node_id)

        if node_id in completed:
            states[node_id] = NodeState(id=node_id, status="done")
            continue

        unmet = [dep for dep in node.requires if dep not in completed]
        if unmet:
            states[node_id] = NodeState(id=node_id, status="blocked", missing_deps=sorted(unmet))
            continue

        outcome = outcomes.get(node_id)
        if outcome is not None and not outcome.passed:
            assert node.gate is not None
            used = count_rollbacks(change_dir, node_id)
            status = "exhausted" if used >= node.gate.on_fail.max_retries else "failed"
            states[node_id] = NodeState(
                id=node_id,
                status=status,
                verdict=outcome,
                rollbacks_used=used,
                max_retries=node.gate.on_fail.max_retries,
            )
            continue

        states[node_id] = NodeState(id=node_id, status="ready")

    return states


def is_complete(states: dict[str, NodeState]) -> bool:
    return all(state.status == "done" for state in states.values())
