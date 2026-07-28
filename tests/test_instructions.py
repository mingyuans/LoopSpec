from pathlib import Path

from loopspec.change_state import create_initial_state
from loopspec.instructions import build_instructions
from loopspec.schema_loader import load_schema

SCHEMA_YAML = """
name: sample
version: 1
nodes:
  - id: proposal
    generates: proposal.md
    description: Initial proposal
    template: proposal.md
    requires: []
    instruction: "Write the proposal."
  - id: design
    generates: design.md
    description: Technical design
    template: design.md
    requires: [proposal]
    instruction:
      file: design.md
  - id: security
    generates: null
    description: Security review
    template: null
    requires: [design]
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

TEMPLATES = {
    "proposal.md": "# Proposal template",
    "design.md": "# Design template",
    "security-pass.md": "# Pass template",
    "security-fail.md": "# Fail template",
}

INSTRUCTIONS = {"design.md": "Write the design doc carefully."}


def build_schema_dir(schema_dir: Path) -> None:
    schema_dir.mkdir(parents=True, exist_ok=True)
    (schema_dir / "schema.yaml").write_text(SCHEMA_YAML, encoding="utf-8")
    templates_dir = schema_dir / "templates"
    templates_dir.mkdir()
    for name, content in TEMPLATES.items():
        (templates_dir / name).write_text(content, encoding="utf-8")
    instructions_dir = schema_dir / "instructions"
    instructions_dir.mkdir()
    for name, content in INSTRUCTIONS.items():
        (instructions_dir / name).write_text(content, encoding="utf-8")


def test_plain_node_has_single_template_and_output_path(tmp_path: Path):
    schema_dir = tmp_path / "schema"
    build_schema_dir(schema_dir)
    change_dir = tmp_path / "change"
    change_dir.mkdir()
    create_initial_state(change_dir)

    loaded = load_schema(schema_dir)
    response = build_instructions(loaded, "proposal", change_dir, change_dir)

    assert response["template"] == "# Proposal template"
    assert response["outputPath"] == "proposal.md"
    assert "templates" not in response


def test_gate_node_has_pass_fail_templates(tmp_path: Path):
    schema_dir = tmp_path / "schema"
    build_schema_dir(schema_dir)
    change_dir = tmp_path / "change"
    change_dir.mkdir()
    create_initial_state(change_dir)
    (change_dir / "proposal.md").write_text("# p")
    (change_dir / "design.md").write_text("# d")

    loaded = load_schema(schema_dir)
    response = build_instructions(loaded, "security", change_dir, change_dir)

    assert response["templates"]["pass"] == "# Pass template"
    assert response["templates"]["fail"] == "# Fail template"
    assert response["outputPath"] == {"pass": "security/pass.md", "fail": "security/fail.md"}
    assert "template" not in response


def test_instruction_file_content_is_expanded_not_path(tmp_path: Path):
    schema_dir = tmp_path / "schema"
    build_schema_dir(schema_dir)
    change_dir = tmp_path / "change"
    change_dir.mkdir()
    create_initial_state(change_dir)
    (change_dir / "proposal.md").write_text("# p")

    loaded = load_schema(schema_dir)
    response = build_instructions(loaded, "design", change_dir, change_dir)

    assert response["instruction"] == "Write the design doc carefully."


def test_context_and_matching_rules_injected(tmp_path: Path):
    schema_dir = tmp_path / "schema"
    build_schema_dir(schema_dir)
    change_dir = tmp_path / "change"
    change_dir.mkdir()
    create_initial_state(change_dir)

    loaded = load_schema(schema_dir)
    response = build_instructions(
        loaded,
        "proposal",
        change_dir,
        change_dir,
        context="This is a payment gateway project.",
        rules_by_node={"proposal": ["Keep it under 500 words"], "design": ["Some other rule"]},
    )

    assert response["context"] == "This is a payment gateway project."
    assert response["rules"] == ["Keep it under 500 words"]


def test_rules_for_unknown_node_warns_but_does_not_crash(tmp_path: Path):
    schema_dir = tmp_path / "schema"
    build_schema_dir(schema_dir)
    change_dir = tmp_path / "change"
    change_dir.mkdir()
    create_initial_state(change_dir)

    loaded = load_schema(schema_dir)
    response = build_instructions(
        loaded,
        "proposal",
        change_dir,
        change_dir,
        rules_by_node={"not-a-real-node": ["irrelevant"]},
    )

    assert any("not-a-real-node" in warning for warning in response["warnings"])


def test_dependencies_and_unlocks_are_correct(tmp_path: Path):
    schema_dir = tmp_path / "schema"
    build_schema_dir(schema_dir)
    change_dir = tmp_path / "change"
    change_dir.mkdir()
    create_initial_state(change_dir)
    (change_dir / "proposal.md").write_text("# p")

    loaded = load_schema(schema_dir)
    response = build_instructions(loaded, "design", change_dir, change_dir)

    assert response["dependencies"] == [
        {
            "id": "proposal",
            "done": True,
            "path": "proposal.md",
            "resolvedPath": str((change_dir / "proposal.md").resolve()),
            "description": "Initial proposal",
        }
    ]
    assert response["unlocks"] == ["security"]


def test_state_field_populated_when_state_md_exists(tmp_path: Path):
    schema_dir = tmp_path / "schema"
    build_schema_dir(schema_dir)
    change_dir = tmp_path / "change"
    change_dir.mkdir()
    create_initial_state(change_dir)

    loaded = load_schema(schema_dir)
    response = build_instructions(loaded, "proposal", change_dir, change_dir)

    assert response["state"] is not None
    assert response["warnings"] == []


def test_state_missing_warns_but_still_returns_instructions(tmp_path: Path):
    schema_dir = tmp_path / "schema"
    build_schema_dir(schema_dir)
    change_dir = tmp_path / "change"
    change_dir.mkdir()  # no state.md created

    loaded = load_schema(schema_dir)
    response = build_instructions(loaded, "proposal", change_dir, change_dir)

    assert response["state"] is None
    assert "state_missing" in response["warnings"]


def test_prior_attempts_empty_for_fresh_node(tmp_path: Path):
    schema_dir = tmp_path / "schema"
    build_schema_dir(schema_dir)
    change_dir = tmp_path / "change"
    change_dir.mkdir()
    create_initial_state(change_dir)

    loaded = load_schema(schema_dir)
    response = build_instructions(loaded, "design", change_dir, change_dir)
    assert response["priorAttempts"] == []


def test_prior_attempts_present_after_rollback(tmp_path: Path):
    import yaml

    schema_dir = tmp_path / "schema"
    build_schema_dir(schema_dir)
    change_dir = tmp_path / "change"
    change_dir.mkdir()
    create_initial_state(change_dir)

    round_dir = change_dir / ".attempts" / "round-001"
    round_dir.mkdir(parents=True)
    (round_dir / "design.md").write_text("# old design")
    meta = {
        "round": 1,
        "gate": "security",
        "verdict": "FAIL",
        "summary": "found issues",
        "blocking_issues": ["sql injection"],
        "archived_files": ["design.md"],
    }
    (round_dir / "_meta.yaml").write_text(yaml.safe_dump(meta))

    loaded = load_schema(schema_dir)
    response = build_instructions(loaded, "design", change_dir, change_dir)

    assert len(response["priorAttempts"]) == 1
    assert response["priorAttempts"][0]["blockingIssues"] == ["sql injection"]
