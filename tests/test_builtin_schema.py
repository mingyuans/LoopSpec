"""Structural contract of the shipped `secure-spec-driven` schema.

Loaded from a real `loopspec init` copy, so this also covers the built-in schema
actually reaching a workflow home intact.
"""

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from loopspec.cli import app
from loopspec.gate_outcome import extract_failure_notes
from loopspec.schema_loader import LoadedSchema, load_schema

runner = CliRunner()


@pytest.fixture
def builtin(tmp_path: Path) -> LoadedSchema:
    home = tmp_path / "wf"
    result = runner.invoke(app, ["init", str(home), "--tools", "none", "--json"])
    assert result.exit_code == 0
    assert json.loads(result.stdout)["copiedSchemas"] == ["secure-spec-driven"]
    return load_schema(home / "schemas" / "secure-spec-driven")


def test_build_order_ends_with_approval_then_apply(builtin: LoadedSchema):
    assert builtin.graph.build_order() == [
        "proposal",
        "design",
        "specs",
        "tasks",
        "security",
        "approval",
        "apply",
    ]


def test_node_dependencies(builtin: LoadedSchema):
    requires = {node_id: builtin.node(node_id).requires for node_id in builtin.graph.node_ids()}
    assert requires == {
        "proposal": [],
        "specs": ["proposal"],
        "design": ["proposal"],
        "tasks": ["specs", "design"],
        "security": ["tasks"],
        "approval": ["security"],
        "apply": ["approval"],
    }


def test_approval_gate_configuration(builtin: LoadedSchema):
    node = builtin.node("approval")
    assert node.gate is not None
    assert node.generates is None and node.template is None
    assert node.gate.outputs.pass_ == "approval/approved.md"
    assert node.gate.outputs.fail == "approval/changes-requested.md"
    # Human feedback reaches "what", not just "how", so specs is reset too.
    assert node.gate.on_fail.reset == ["specs", "design"]
    assert node.gate.on_fail.max_retries == 5
    assert node.gate.on_fail.on_exhausted == "escalate"


def test_apply_gate_configuration(builtin: LoadedSchema):
    node = builtin.node("apply")
    assert node.gate is not None
    assert node.generates is None and node.template is None
    assert node.tracks == "tasks.md"
    assert node.gate.outputs.pass_ == "apply/report.md"
    assert node.gate.outputs.fail == "apply/blocked.md"
    assert node.gate.on_fail.reset == ["design"]
    assert node.gate.on_fail.max_retries == 2
    assert node.gate.on_fail.on_exhausted == "escalate"


def test_every_node_has_an_instruction(builtin: LoadedSchema):
    for node_id in builtin.graph.node_ids():
        assert builtin.instructions[node_id].strip(), f"{node_id} has no instruction"


def test_gate_templates_exist(builtin: LoadedSchema):
    templates = builtin.schema_dir / "templates"
    for name in (
        "approval-approved.md",
        "approval-changes-requested.md",
        "apply-report.md",
        "apply-blocked.md",
    ):
        assert (templates / name).is_file(), f"missing template {name}"


def test_approval_instruction_requires_asking_a_human(builtin: LoadedSchema):
    instruction = builtin.instructions["approval"]
    assert "AskUserQuestion" in instruction
    assert "Never approve on the human's behalf" in instruction
    assert "write *neither* output and stop" in instruction


def test_approval_instruction_requires_state_md_write_back(builtin: LoadedSchema):
    instruction = builtin.instructions["approval"]
    assert "state.md" in instruction
    for section in (
        "Decision Log",
        "Frozen Decisions",
        "Rejected Options",
        "Open Questions",
        "Current Focus",
        "Artifact Notes",
    ):
        assert section in instruction, f"approval instruction never mentions {section}"
    assert "Append only" in instruction
    assert "state_missing" in instruction


def test_approval_instruction_splits_verbatim_from_distilled(builtin: LoadedSchema):
    instruction = builtin.instructions["approval"]
    # Verbatim words live in the verdict file; state.md gets distilled entries...
    assert "verbatim" in instruction
    assert "not in `state.md`" in instruction
    # ...and every entry must resolve without this conversation's context.
    assert "Replace every pronoun and deictic reference" in instruction
    assert '"that"' in instruction


def test_approval_templates_carry_quote_and_write_back_sections(builtin: LoadedSchema):
    templates = builtin.schema_dir / "templates"
    for name in ("approval-approved.md", "approval-changes-requested.md"):
        body = (templates / name).read_text(encoding="utf-8")
        assert "## Human's Words" in body, f"{name} has nowhere for the verbatim quote"
        assert "## state.md Write-Back" in body, f"{name} cannot be audited for write-back"


def test_fail_templates_expose_bullets_to_failure_extraction(builtin: LoadedSchema):
    templates = builtin.schema_dir / "templates"
    for name, heading in (
        ("approval-changes-requested.md", "Human Approval: CHANGES REQUESTED"),
        ("apply-blocked.md", "Implementation Blocked"),
        ("security-fail.md", "Security Review: FAIL"),
    ):
        summary, issues = extract_failure_notes((templates / name).read_text(encoding="utf-8"))
        assert summary == heading
        assert issues, f"{name} has no bullet list for blockingIssues"


def test_apply_instruction_covers_the_implementation_loop(builtin: LoadedSchema):
    instruction = builtin.instructions["apply"]
    assert "contextFiles" in instruction
    assert "taskProgress" in instruction
    assert "`- [ ]` to\n   `- [x]`" in instruction
    assert "make test" in instruction
    assert "only `done` when every checkbox" in instruction


def test_apply_instruction_requires_recording_landed_code_changes(builtin: LoadedSchema):
    instruction = builtin.instructions["apply"]
    assert "Record the code changes you already made" in instruction
    assert "does not revert a single" in instruction
    blocked = (builtin.schema_dir / "templates" / "apply-blocked.md").read_text(encoding="utf-8")
    assert "## Code Changes Already Made" in blocked
