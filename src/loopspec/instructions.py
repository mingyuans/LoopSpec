"""Instruction response assembly for a given node."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .attempts import prior_attempts_for_node
from .change_state import read_state_for_instruction
from .errors import NodeNotFoundError
from .schema_loader import LoadedSchema
from .state import compute_states


def build_instructions(
    loaded: LoadedSchema,
    node_id: str,
    change_dir: Path,
    artifact_dir: Path,
    context: str | None = None,
    rules_by_node: dict[str, list[str]] | None = None,
) -> dict[str, Any]:
    """Assemble the full `loopspec instructions` response for one node."""

    if node_id not in loaded.graph.node_ids():
        raise NodeNotFoundError(f"Node not found: {node_id}")

    node = loaded.node(node_id)
    rules_by_node = rules_by_node or {}
    known_ids = set(loaded.graph.node_ids())
    warnings: list[str] = [
        f"rules reference unknown node '{key}'" for key in rules_by_node if key not in known_ids
    ]

    states = compute_states(loaded.graph, change_dir, artifact_dir)

    dependencies = []
    for dep_id in node.requires:
        dep_node = loaded.node(dep_id)
        dep_path = (
            dep_node.gate.outputs.pass_ if dep_node.gate is not None else dep_node.generates
        )
        dependencies.append(
            {
                "id": dep_id,
                "done": states[dep_id].status == "done",
                "path": dep_path,
                "resolvedPath": str((artifact_dir / dep_path).resolve()) if dep_path else None,
                "description": dep_node.description,
            }
        )

    state_text, state_warnings = read_state_for_instruction(change_dir)
    warnings.extend(state_warnings)

    response: dict[str, Any] = {
        "nodeId": node_id,
        "description": node.description,
        "instruction": loaded.instructions.get(node_id, ""),
        "context": context,
        "rules": rules_by_node.get(node_id, []),
        "dependencies": dependencies,
        "unlocks": loaded.graph.dependents(node_id),
        "statePath": str((change_dir / "state.md").resolve()),
        "state": state_text,
        "warnings": warnings,
        "priorAttempts": prior_attempts_for_node(change_dir, node),
    }

    if node.gate is None:
        assert node.generates is not None and node.template is not None
        response["outputPath"] = node.generates
        response["resolvedOutputPath"] = str((artifact_dir / node.generates).resolve())
        response["template"] = _read_template(loaded.schema_dir, node.template)
    else:
        response["outputPath"] = {
            "pass": node.gate.outputs.pass_,
            "fail": node.gate.outputs.fail,
        }
        response["resolvedOutputPath"] = {
            "pass": str((artifact_dir / node.gate.outputs.pass_).resolve()),
            "fail": str((artifact_dir / node.gate.outputs.fail).resolve()),
        }
        response["templates"] = {
            "pass": _read_template(loaded.schema_dir, node.gate.templates.pass_),
            "fail": _read_template(loaded.schema_dir, node.gate.templates.fail),
        }

    return response


def _read_template(schema_dir: Path, template_name: str) -> str:
    return (schema_dir / "templates" / template_name).read_text(encoding="utf-8")
