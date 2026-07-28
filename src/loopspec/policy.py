"""nextSteps generation policy."""

from __future__ import annotations

from .graph import WorkflowGraph
from .models import OnExhausted
from .state import NodeState


def build_next_steps(
    change_name: str, graph: WorkflowGraph, states: dict[str, NodeState]
) -> list[str]:
    """`exhausted` > `failed` > first `ready` > all-done, in that priority order."""

    build_order = graph.build_order()

    for node_id in build_order:
        state = states[node_id]
        if state.status != "exhausted":
            continue
        node = graph.node(node_id)
        assert node.gate is not None
        if node.gate.on_fail.on_exhausted is OnExhausted.ESCALATE:
            return [
                f'Gate "{node_id}" has failed {state.rollbacks_used} rollback attempt(s) '
                "and reached its retry limit; human intervention is required.",
                f"Run `loopspec history {change_name} --json` to review past failures.",
            ]
        return [f'Gate "{node_id}" failed and retries are exhausted; the workflow stops.']

    for node_id in build_order:
        state = states[node_id]
        if state.status != "failed":
            continue
        summary = state.verdict.summary if state.verdict else None
        return [
            f'Gate "{node_id}" verdict is FAIL: {summary or "no summary provided"}',
            f"Run `loopspec rollback {change_name} --json` to roll back, "
            "then regenerate the reset nodes.",
        ]

    for node_id in build_order:
        if states[node_id].status == "ready":
            return [
                f'Run `loopspec instructions {node_id} --change "{change_name}" --json`, '
                "then write the artifact per the returned template(s) and update state.md."
            ]

    return ["All nodes are complete."]
