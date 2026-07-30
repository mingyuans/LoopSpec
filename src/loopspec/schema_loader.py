"""Schema loading: structural validation followed by semantic validation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml
from pydantic import ValidationError

from .errors import (
    InstructionLoadError,
    SchemaNotFoundError,
    SchemaValidationError,
    TemplateLoadError,
)
from .graph import WorkflowGraph
from .models import InstructionRef, NodeSpec, WorkflowSchema
from .outputs import is_glob

_RESERVED_OUTPUT_NAMES = {"state.md", ".workflow.yaml"}


@dataclass
class LoadedSchema:
    """A fully validated schema, ready for graph/state operations."""

    schema: WorkflowSchema
    graph: WorkflowGraph
    schema_dir: Path
    instructions: dict[str, str]

    @property
    def name(self) -> str:
        return self.schema.name

    def node(self, node_id: str) -> NodeSpec:
        return self.graph.node(node_id)


def load_schema(schema_dir: Path) -> LoadedSchema:
    """Load and fully validate a schema.yaml under `schema_dir`."""

    schema_file = schema_dir / "schema.yaml"
    if not schema_file.is_file():
        raise SchemaNotFoundError(
            f"Schema file not found: {schema_file}",
            fix="Create a schema.yaml in this directory or point to the correct schema directory.",
        )

    raw = yaml.safe_load(schema_file.read_text(encoding="utf-8")) or {}
    try:
        schema = WorkflowSchema.model_validate(raw)
    except ValidationError as exc:
        raise SchemaValidationError(str(exc)) from exc

    _validate_unique_ids(schema.nodes)
    nodes = {node.id: node for node in schema.nodes}
    _validate_requires_exist(nodes)

    graph = WorkflowGraph(schema)  # raises SchemaValidationError on cycles

    for node in schema.nodes:
        if node.gate is None:
            _validate_plain_node(node, schema_dir)
        else:
            _validate_gate_node(node, schema_dir)
        _validate_output_paths(node)

    for node in schema.nodes:
        if node.gate is not None:
            _validate_reset_ancestors(node, graph)
        _validate_tracks(node, nodes, graph)

    instructions = {
        node.id: _resolve_instruction(node, schema_dir)
        for node in schema.nodes
        if node.instruction is not None
    }

    return LoadedSchema(
        schema=schema, graph=graph, schema_dir=schema_dir, instructions=instructions
    )


def _validate_unique_ids(nodes: list[NodeSpec]) -> None:
    seen: set[str] = set()
    for node in nodes:
        if node.id in seen:
            raise SchemaValidationError(
                f"Duplicate node id: {node.id}",
                fix="Rename one of the duplicate node ids so each is unique.",
            )
        seen.add(node.id)


def _validate_requires_exist(nodes: dict[str, NodeSpec]) -> None:
    for node in nodes.values():
        for dep in node.requires:
            if dep not in nodes:
                raise SchemaValidationError(
                    f"Node '{node.id}' requires unknown node '{dep}'",
                    fix=f"Add a node with id '{dep}', or fix the typo in '{node.id}'.requires.",
                )


def _is_safe_relative_path(path: str) -> bool:
    if not path:
        return False
    parsed = Path(path)
    if parsed.is_absolute():
        return False
    if ".." in parsed.parts:
        return False
    return True


def _check_template_exists(label: str, template_name: str, templates_dir: Path) -> None:
    if not _is_safe_relative_path(template_name):
        raise SchemaValidationError(
            f"{label} template path must be relative and stay under templates/: {template_name}"
        )
    resolved_dir = templates_dir.resolve()
    target = (templates_dir / template_name).resolve()
    if target != resolved_dir and resolved_dir not in target.parents:
        raise SchemaValidationError(
            f"{label} template path must be relative and stay under templates/: {template_name}"
        )
    if not target.is_file():
        raise TemplateLoadError(f"Template not found: templates/{template_name}")


def _validate_plain_node(node: NodeSpec, schema_dir: Path) -> None:
    if not isinstance(node.generates, str) or not node.generates:
        raise SchemaValidationError(f"Node '{node.id}' generates must be a path string")
    if not isinstance(node.template, str) or not node.template:
        raise SchemaValidationError(f"Node '{node.id}' template must be a template file")
    _check_template_exists(f"Node '{node.id}'", node.template, schema_dir / "templates")


def _validate_gate_node(node: NodeSpec, schema_dir: Path) -> None:
    gate = node.gate
    assert gate is not None
    if node.generates is not None and not isinstance(node.generates, str):
        raise SchemaValidationError(f"Gate '{node.id}' generates must be null or a path string")
    if node.template is not None and not isinstance(node.template, str):
        raise SchemaValidationError(f"Gate '{node.id}' template must be null or a template file")

    pass_path, fail_path = gate.outputs.pass_, gate.outputs.fail
    if is_glob(pass_path) or is_glob(fail_path) or pass_path == fail_path:
        raise SchemaValidationError(
            f"Gate '{node.id}' pass/fail outputs must be concrete distinct paths"
        )

    templates_dir = schema_dir / "templates"
    _check_template_exists(f"Gate '{node.id}'", gate.templates.pass_, templates_dir)
    _check_template_exists(f"Gate '{node.id}'", gate.templates.fail, templates_dir)


def _validate_output_paths(node: NodeSpec) -> None:
    """Every path a node writes must be a safe relative path, and not a reserved name.

    Containment is not merely tidiness. An output path is also what `rollback`
    resolves and *moves* into `.attempts/`, so `../other-change/proposal.md` would
    let one change's gate failure carry off another change's artifacts -- and since
    all state is derived from the filesystem, that silently un-completes work
    nobody touched.
    """

    candidates: list[str] = []
    if isinstance(node.generates, str):
        candidates.append(node.generates)
    if node.gate is not None:
        candidates.append(node.gate.outputs.pass_)
        candidates.append(node.gate.outputs.fail)
    for candidate in candidates:
        if not _is_safe_relative_path(candidate):
            raise SchemaValidationError(
                f"Node '{node.id}' output path must be relative and stay inside the "
                f"change directory: {candidate}",
                fix="Use a path relative to the artifact root, e.g. 'proposal.md'. "
                "A node cannot declare an output outside its own change.",
            )
        if candidate in _RESERVED_OUTPUT_NAMES:
            raise SchemaValidationError(
                f"Output path '{candidate}' is reserved",
                fix="'state.md' and '.workflow.yaml' are reserved for change metadata; "
                "choose a different output path.",
            )


def _validate_reset_ancestors(node: NodeSpec, graph: WorkflowGraph) -> None:
    gate = node.gate
    assert gate is not None
    all_ids = set(graph.node_ids())
    ancestors = graph.ancestors(node.id)
    for target in gate.on_fail.reset:
        if target not in all_ids:
            raise SchemaValidationError(
                f"Gate '{node.id}' resets unknown node '{target}'",
                fix=f"Add a node with id '{target}', or fix the typo in on_fail.reset.",
            )
        if target not in ancestors:
            raise SchemaValidationError(
                f"Gate '{node.id}' cannot reset '{target}': not an ancestor",
                fix=f"on_fail.reset must reference an ancestor of '{node.id}'. "
                f"Valid choices: {sorted(ancestors)}",
            )


def _validate_tracks(node: NodeSpec, nodes: dict[str, NodeSpec], graph: WorkflowGraph) -> None:
    """`tracks` must name a concrete artifact produced by one of this node's ancestors."""

    tracks = node.tracks
    if tracks is None:
        return

    if not _is_safe_relative_path(tracks):
        raise SchemaValidationError(
            f"Node '{node.id}' tracks must be a relative path without '..': {tracks}",
            fix="Use a path relative to the artifact root, e.g. 'tasks.md'.",
        )
    if is_glob(tracks):
        raise SchemaValidationError(
            f"Node '{node.id}' tracks must be a concrete file path, not a glob: {tracks}",
            fix="Progress has to come from one definite file; point tracks at a single "
            "checkbox file such as 'tasks.md'.",
        )

    producers = sorted(other.id for other in nodes.values() if other.generates == tracks)
    if not producers:
        raise SchemaValidationError(
            f"Node '{node.id}' tracks '{tracks}', which no node declares in `generates`",
            fix=f"Set '{node.id}'.tracks to a path some node generates, or add a node "
            f"generating '{tracks}'.",
        )

    ancestors = graph.ancestors(node.id)
    if not any(producer in ancestors for producer in producers):
        raise SchemaValidationError(
            f"Node '{node.id}' cannot track '{tracks}': it is produced by {producers}, "
            f"which is not an ancestor of '{node.id}'",
            fix=f"The tracked file must already exist when '{node.id}' runs. Add the "
            f"producing node to '{node.id}'.requires (directly or transitively). "
            f"Current ancestors: {sorted(ancestors)}",
        )


def _resolve_instruction(node: NodeSpec, schema_dir: Path) -> str:
    instruction = node.instruction
    if isinstance(instruction, str):
        return instruction

    assert isinstance(instruction, InstructionRef)
    if not _is_safe_relative_path(instruction.file):
        raise SchemaValidationError(
            f"Instruction path must be relative and safe: {instruction.file}"
        )
    instructions_dir = (schema_dir / "instructions").resolve()
    target = (instructions_dir / instruction.file).resolve()
    if target != instructions_dir and instructions_dir not in target.parents:
        raise SchemaValidationError(
            f"Instruction path must stay under instructions/: {instruction.file}"
        )
    if not target.is_file():
        raise InstructionLoadError(f"Instruction not found: instructions/{instruction.file}")
    return target.read_text(encoding="utf-8")
