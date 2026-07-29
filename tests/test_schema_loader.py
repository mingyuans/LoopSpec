from pathlib import Path

import pytest

from loopspec.errors import (
    InstructionLoadError,
    SchemaValidationError,
    TemplateLoadError,
)
from loopspec.schema_loader import load_schema


def _write(schema_dir: Path, schema_yaml: str, templates: dict[str, str] | None = None,
           instructions: dict[str, str] | None = None) -> None:
    schema_dir.mkdir(parents=True, exist_ok=True)
    (schema_dir / "schema.yaml").write_text(schema_yaml, encoding="utf-8")
    templates_dir = schema_dir / "templates"
    templates_dir.mkdir(exist_ok=True)
    for name, content in (templates or {}).items():
        path = templates_dir / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    if instructions:
        instructions_dir = schema_dir / "instructions"
        instructions_dir.mkdir(exist_ok=True)
        for name, content in instructions.items():
            (instructions_dir / name).write_text(content, encoding="utf-8")


VALID_SCHEMA = """
name: sample
version: 1
nodes:
  - id: proposal
    generates: proposal.md
    description: proposal
    template: proposal.md
    requires: []
  - id: design
    generates: design.md
    description: design
    template: design.md
    requires: [proposal]
  - id: tasks
    generates: tasks.md
    description: tasks
    template: tasks.md
    requires: [design]
  - id: security
    generates: null
    description: security review
    template: null
    requires: [tasks]
    gate:
      outputs:
        pass: security/pass.md
        fail: security/fail.md
      templates:
        pass: security-pass.md
        fail: security-fail.md
      on_fail:
        reset: [design]
        max_retries: 3
"""

VALID_TEMPLATES = {
    "proposal.md": "# proposal",
    "design.md": "# design",
    "tasks.md": "# tasks",
    "security-pass.md": "# pass",
    "security-fail.md": "# fail",
}


def test_valid_schema_loads(tmp_path: Path):
    _write(tmp_path, VALID_SCHEMA, VALID_TEMPLATES)
    loaded = load_schema(tmp_path)
    assert loaded.graph.build_order() == ["proposal", "design", "tasks", "security"]


def test_unknown_field_rejected(tmp_path: Path):
    schema_yaml = """
name: sample
version: 1
nodes:
  - id: proposal
    generates: proposal.md
    description: proposal
    template: proposal.md
    require: []
"""
    _write(tmp_path, schema_yaml, {"proposal.md": "# x"})
    with pytest.raises(SchemaValidationError):
        load_schema(tmp_path)


def test_duplicate_node_id_rejected(tmp_path: Path):
    schema_yaml = """
name: sample
version: 1
nodes:
  - id: proposal
    generates: a.md
    description: a
    template: a.md
    requires: []
  - id: proposal
    generates: b.md
    description: b
    template: b.md
    requires: []
"""
    _write(tmp_path, schema_yaml, {"a.md": "# a", "b.md": "# b"})
    with pytest.raises(SchemaValidationError, match="Duplicate node id"):
        load_schema(tmp_path)


def test_requires_unknown_node_rejected(tmp_path: Path):
    schema_yaml = """
name: sample
version: 1
nodes:
  - id: tasks
    generates: tasks.md
    description: tasks
    template: tasks.md
    requires: [desgin]
"""
    _write(tmp_path, schema_yaml, {"tasks.md": "# tasks"})
    with pytest.raises(SchemaValidationError, match="desgin"):
        load_schema(tmp_path)


def test_cyclic_requires_rejected(tmp_path: Path):
    schema_yaml = """
name: sample
version: 1
nodes:
  - id: a
    generates: a.md
    description: a
    template: a.md
    requires: [b]
  - id: b
    generates: b.md
    description: b
    template: b.md
    requires: [a]
"""
    _write(tmp_path, schema_yaml, {"a.md": "# a", "b.md": "# b"})
    with pytest.raises(SchemaValidationError):
        load_schema(tmp_path)


def test_plain_node_missing_generates_rejected(tmp_path: Path):
    schema_yaml = """
name: sample
version: 1
nodes:
  - id: proposal
    description: proposal
    template: proposal.md
    requires: []
"""
    _write(tmp_path, schema_yaml, {"proposal.md": "# x"})
    with pytest.raises(SchemaValidationError):
        load_schema(tmp_path)


def test_missing_template_file_rejected(tmp_path: Path):
    schema_yaml = """
name: sample
version: 1
nodes:
  - id: proposal
    generates: proposal.md
    description: proposal
    template: missing.md
    requires: []
"""
    _write(tmp_path, schema_yaml)
    with pytest.raises(TemplateLoadError):
        load_schema(tmp_path)


GATE_BASE = """
name: sample
version: 1
nodes:
  - id: design
    generates: design.md
    description: design
    template: design.md
    requires: []
  - id: security
    generates: null
    description: security review
    template: null
    requires: [design]
    gate:
{gate_body}
"""


def test_gate_with_null_generates_and_outputs_passes(tmp_path: Path):
    gate_body = """      outputs:
        pass: security/pass.md
        fail: security/fail.md
      templates:
        pass: security-pass.md
        fail: security-fail.md
      on_fail:
        reset: [design]
"""
    schema_yaml = GATE_BASE.format(gate_body=gate_body)
    _write(
        tmp_path,
        schema_yaml,
        {"design.md": "# design", "security-pass.md": "# pass", "security-fail.md": "# fail"},
    )
    loaded = load_schema(tmp_path)
    assert loaded.node("security").gate is not None


def test_gate_missing_outputs_rejected(tmp_path: Path):
    schema_yaml = """
name: sample
version: 1
nodes:
  - id: design
    generates: design.md
    description: design
    template: design.md
    requires: []
  - id: security
    generates: null
    description: security
    template: null
    requires: [design]
    gate:
      templates:
        pass: security-pass.md
        fail: security-fail.md
      on_fail:
        reset: [design]
"""
    _write(
        tmp_path,
        schema_yaml,
        {"design.md": "# d", "security-pass.md": "# p", "security-fail.md": "# f"},
    )
    with pytest.raises(SchemaValidationError):
        load_schema(tmp_path)


def test_gate_missing_templates_rejected(tmp_path: Path):
    schema_yaml = """
name: sample
version: 1
nodes:
  - id: design
    generates: design.md
    description: design
    template: design.md
    requires: []
  - id: security
    generates: null
    description: security
    template: null
    requires: [design]
    gate:
      outputs:
        pass: security/pass.md
        fail: security/fail.md
      on_fail:
        reset: [design]
"""
    _write(tmp_path, schema_yaml, {"design.md": "# d"})
    with pytest.raises(SchemaValidationError):
        load_schema(tmp_path)


def test_gate_glob_outputs_rejected(tmp_path: Path):
    gate_body = """      outputs:
        pass: "security/*.md"
        fail: security/fail.md
      templates:
        pass: security-pass.md
        fail: security-fail.md
      on_fail:
        reset: [design]
"""
    schema_yaml = GATE_BASE.format(gate_body=gate_body)
    _write(
        tmp_path,
        schema_yaml,
        {"design.md": "# d", "security-pass.md": "# p", "security-fail.md": "# f"},
    )
    with pytest.raises(SchemaValidationError):
        load_schema(tmp_path)


def test_gate_identical_outputs_rejected(tmp_path: Path):
    gate_body = """      outputs:
        pass: security/verdict.md
        fail: security/verdict.md
      templates:
        pass: security-pass.md
        fail: security-fail.md
      on_fail:
        reset: [design]
"""
    schema_yaml = GATE_BASE.format(gate_body=gate_body)
    _write(
        tmp_path,
        schema_yaml,
        {"design.md": "# d", "security-pass.md": "# p", "security-fail.md": "# f"},
    )
    with pytest.raises(SchemaValidationError):
        load_schema(tmp_path)


def test_gate_missing_template_file_rejected(tmp_path: Path):
    gate_body = """      outputs:
        pass: security/pass.md
        fail: security/fail.md
      templates:
        pass: missing-pass.md
        fail: security-fail.md
      on_fail:
        reset: [design]
"""
    schema_yaml = GATE_BASE.format(gate_body=gate_body)
    _write(tmp_path, schema_yaml, {"design.md": "# d", "security-fail.md": "# f"})
    with pytest.raises(TemplateLoadError):
        load_schema(tmp_path)


THREE_LEVEL_SCHEMA = """
name: sample
version: 1
nodes:
  - id: proposal
    generates: proposal.md
    description: proposal
    template: proposal.md
    requires: []
  - id: design
    generates: design.md
    description: design
    template: design.md
    requires: [proposal]
  - id: tasks
    generates: tasks.md
    description: tasks
    template: tasks.md
    requires: [design]
  - id: security
    generates: null
    description: security
    template: null
    requires: [tasks]
    gate:
      outputs:
        pass: security/pass.md
        fail: security/fail.md
      templates:
        pass: security-pass.md
        fail: security-fail.md
      on_fail:
        reset: [{reset_target}]
"""

THREE_LEVEL_TEMPLATES = {
    "proposal.md": "# p",
    "design.md": "# d",
    "tasks.md": "# t",
    "security-pass.md": "# pass",
    "security-fail.md": "# fail",
}


def test_reset_unknown_node_rejected(tmp_path: Path):
    schema_yaml = THREE_LEVEL_SCHEMA.format(reset_target="desgin")
    _write(tmp_path, schema_yaml, THREE_LEVEL_TEMPLATES)
    with pytest.raises(SchemaValidationError, match="desgin"):
        load_schema(tmp_path)


def test_reset_non_ancestor_rejected(tmp_path: Path):
    schema_yaml = """
name: sample
version: 1
nodes:
  - id: proposal
    generates: proposal.md
    description: proposal
    template: proposal.md
    requires: []
  - id: unrelated
    generates: unrelated.md
    description: unrelated
    template: unrelated.md
    requires: []
  - id: security
    generates: null
    description: security
    template: null
    requires: [proposal]
    gate:
      outputs:
        pass: security/pass.md
        fail: security/fail.md
      templates:
        pass: security-pass.md
        fail: security-fail.md
      on_fail:
        reset: [unrelated]
"""
    _write(
        tmp_path,
        schema_yaml,
        {
            "proposal.md": "# p",
            "unrelated.md": "# u",
            "security-pass.md": "# pass",
            "security-fail.md": "# fail",
        },
    )
    with pytest.raises(SchemaValidationError, match="not an ancestor"):
        load_schema(tmp_path)


def test_reset_direct_ancestor_allowed(tmp_path: Path):
    schema_yaml = THREE_LEVEL_SCHEMA.format(reset_target="tasks")
    _write(tmp_path, schema_yaml, THREE_LEVEL_TEMPLATES)
    load_schema(tmp_path)  # no raise


def test_reset_transitive_ancestor_allowed(tmp_path: Path):
    schema_yaml = THREE_LEVEL_SCHEMA.format(reset_target="proposal")
    _write(tmp_path, schema_yaml, THREE_LEVEL_TEMPLATES)
    load_schema(tmp_path)  # no raise


def test_inline_instruction_string(tmp_path: Path):
    schema_yaml = """
name: sample
version: 1
nodes:
  - id: proposal
    generates: proposal.md
    description: proposal
    template: proposal.md
    requires: []
    instruction: "Write the proposal."
"""
    _write(tmp_path, schema_yaml, {"proposal.md": "# p"})
    loaded = load_schema(tmp_path)
    assert loaded.instructions["proposal"] == "Write the proposal."


def test_instruction_file_reference_loads_content(tmp_path: Path):
    schema_yaml = """
name: sample
version: 1
nodes:
  - id: security
    generates: proposal.md
    description: security
    template: proposal.md
    requires: []
    instruction:
      file: security.md
"""
    _write(
        tmp_path,
        schema_yaml,
        {"proposal.md": "# p"},
        {"security.md": "Review carefully."},
    )
    loaded = load_schema(tmp_path)
    assert loaded.instructions["security"] == "Review carefully."


def test_instruction_file_missing_rejected(tmp_path: Path):
    schema_yaml = """
name: sample
version: 1
nodes:
  - id: security
    generates: proposal.md
    description: security
    template: proposal.md
    requires: []
    instruction:
      file: missing.md
"""
    _write(tmp_path, schema_yaml, {"proposal.md": "# p"})
    with pytest.raises(InstructionLoadError):
        load_schema(tmp_path)


def test_instruction_file_unsafe_path_rejected(tmp_path: Path):
    schema_yaml = """
name: sample
version: 1
nodes:
  - id: security
    generates: proposal.md
    description: security
    template: proposal.md
    requires: []
    instruction:
      file: "../secrets.md"
"""
    _write(tmp_path, schema_yaml, {"proposal.md": "# p"})
    with pytest.raises(SchemaValidationError):
        load_schema(tmp_path)


def test_generates_reserved_name_rejected(tmp_path: Path):
    schema_yaml = """
name: sample
version: 1
nodes:
  - id: proposal
    generates: state.md
    description: proposal
    template: proposal.md
    requires: []
"""
    _write(tmp_path, schema_yaml, {"proposal.md": "# p"})
    with pytest.raises(SchemaValidationError, match="reserved"):
        load_schema(tmp_path)


TRACKS_SCHEMA = """
name: sample
version: 1
nodes:
  - id: proposal
    generates: proposal.md
    description: proposal
    template: proposal.md
    requires: []
  - id: specs
    generates: "specs/**/*.md"
    description: specs
    template: proposal.md
    requires: [proposal]
  - id: tasks
    generates: tasks.md
    description: tasks
    template: tasks.md
    requires: [proposal]
  - id: apply
    generates: null
    description: implementation
    template: null
    requires: [tasks]
    tracks: {tracks}
    gate:
      outputs:
        pass: apply/report.md
        fail: apply/blocked.md
      templates:
        pass: security-pass.md
        fail: security-fail.md
      on_fail:
        reset: [tasks]
"""

TRACKS_TEMPLATES = {
    "proposal.md": "# p",
    "tasks.md": "# t",
    "security-pass.md": "# pass",
    "security-fail.md": "# fail",
}


def test_tracks_pointing_at_ancestor_output_loads(tmp_path: Path):
    _write(tmp_path, TRACKS_SCHEMA.format(tracks="tasks.md"), TRACKS_TEMPLATES)
    loaded = load_schema(tmp_path)
    assert loaded.node("apply").tracks == "tasks.md"


def test_schema_without_tracks_defaults_to_none(tmp_path: Path):
    _write(tmp_path, VALID_SCHEMA, VALID_TEMPLATES)
    loaded = load_schema(tmp_path)
    assert all(loaded.node(node_id).tracks is None for node_id in loaded.graph.node_ids())


def test_tracks_glob_rejected(tmp_path: Path):
    _write(tmp_path, TRACKS_SCHEMA.format(tracks='"specs/**/*.md"'), TRACKS_TEMPLATES)
    with pytest.raises(SchemaValidationError, match="not a glob"):
        load_schema(tmp_path)


def test_tracks_absolute_path_rejected(tmp_path: Path):
    _write(tmp_path, TRACKS_SCHEMA.format(tracks='"/etc/tasks.md"'), TRACKS_TEMPLATES)
    with pytest.raises(SchemaValidationError, match="relative path"):
        load_schema(tmp_path)


def test_tracks_parent_traversal_rejected(tmp_path: Path):
    _write(tmp_path, TRACKS_SCHEMA.format(tracks='"../tasks.md"'), TRACKS_TEMPLATES)
    with pytest.raises(SchemaValidationError, match="relative path"):
        load_schema(tmp_path)


def test_tracks_not_generated_by_any_node_rejected(tmp_path: Path):
    _write(tmp_path, TRACKS_SCHEMA.format(tracks="todo.md"), TRACKS_TEMPLATES)
    with pytest.raises(SchemaValidationError, match="no node declares"):
        load_schema(tmp_path)


def test_tracks_non_ancestor_producer_rejected(tmp_path: Path):
    # `specs` is generated by a node that is not an ancestor of `apply`, and its
    # glob form is rejected anyway -- so use a concrete non-ancestor artifact.
    schema_yaml = """
name: sample
version: 1
nodes:
  - id: proposal
    generates: proposal.md
    description: proposal
    template: proposal.md
    requires: []
  - id: unrelated
    generates: unrelated.md
    description: unrelated
    template: proposal.md
    requires: []
  - id: apply
    generates: null
    description: implementation
    template: null
    requires: [proposal]
    tracks: unrelated.md
    gate:
      outputs:
        pass: apply/report.md
        fail: apply/blocked.md
      templates:
        pass: security-pass.md
        fail: security-fail.md
      on_fail:
        reset: [proposal]
"""
    _write(tmp_path, schema_yaml, TRACKS_TEMPLATES)
    with pytest.raises(SchemaValidationError, match="not an ancestor"):
        load_schema(tmp_path)


def test_gate_output_reserved_name_rejected(tmp_path: Path):
    gate_body = """      outputs:
        pass: state.md
        fail: security/fail.md
      templates:
        pass: security-pass.md
        fail: security-fail.md
      on_fail:
        reset: [design]
"""
    schema_yaml = GATE_BASE.format(gate_body=gate_body)
    _write(
        tmp_path,
        schema_yaml,
        {"design.md": "# d", "security-pass.md": "# p", "security-fail.md": "# f"},
    )
    with pytest.raises(SchemaValidationError, match="reserved"):
        load_schema(tmp_path)
