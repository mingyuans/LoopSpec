from pathlib import Path

import pytest

from loopspec.errors import NoFailedGateError, RetriesExhaustedError
from loopspec.gate_outcome import read_gate_outcome
from loopspec.graph import WorkflowGraph
from loopspec.models import NodeSpec, WorkflowSchema
from loopspec.rollback import compute_reset_closure, execute_rollback, rollback_change
from loopspec.state import compute_states


def make_gate_node(
    node_id: str, requires: list[str], max_retries: int = 3, reset: list[str] | None = None
) -> NodeSpec:
    return NodeSpec(
        id=node_id,
        description=f"gate {node_id}",
        generates=None,
        template=None,
        requires=requires,
        gate={
            "outputs": {"pass": f"{node_id}/pass.md", "fail": f"{node_id}/fail.md"},
            "templates": {"pass": "pass.md", "fail": "fail.md"},
            "on_fail": {"reset": reset or requires, "max_retries": max_retries},
        },
    )


def make_plain_node(node_id: str, requires: list[str] | None = None) -> NodeSpec:
    return NodeSpec(
        id=node_id,
        description=node_id,
        generates=f"{node_id}.md",
        template=f"{node_id}.md",
        requires=requires or [],
    )


def linear_schema_with_gate(max_retries: int = 3) -> WorkflowSchema:
    return WorkflowSchema(
        name="sample",
        version=1,
        nodes=[
            make_plain_node("proposal"),
            make_plain_node("design", ["proposal"]),
            make_plain_node("tasks", ["design"]),
            make_gate_node("security", ["tasks"], max_retries=max_retries, reset=["design"]),
        ],
    )


def seed_failed_change(change_dir: Path) -> WorkflowGraph:
    graph = WorkflowGraph(linear_schema_with_gate())
    for name in ("proposal", "design", "tasks"):
        (change_dir / f"{name}.md").write_text(f"# {name}")
    (change_dir / "security").mkdir()
    (change_dir / "security" / "fail.md").write_text("# Blocked\n\n- injection risk")
    (change_dir / "state.md").write_text("# Change State\n")
    return graph


def test_closure_includes_gate_itself():
    graph = WorkflowGraph(linear_schema_with_gate())
    closure = compute_reset_closure(graph, "security")
    assert "security" in closure


def test_closure_includes_downstream_of_reset_target():
    graph = WorkflowGraph(linear_schema_with_gate())
    closure = compute_reset_closure(graph, "security")
    assert closure == ["design", "tasks", "security"]


def test_closure_is_topologically_ordered():
    graph = WorkflowGraph(linear_schema_with_gate())
    closure = compute_reset_closure(graph, "security")
    order = graph.build_order()
    assert closure == [n for n in order if n in closure]


def test_execute_rollback_removes_original_files(tmp_path: Path):
    graph = seed_failed_change(tmp_path)
    outcome = read_gate_outcome(tmp_path, graph.node("security").gate.outputs)
    execute_rollback(graph, tmp_path, tmp_path, "security", outcome)

    assert not (tmp_path / "design.md").exists()
    assert not (tmp_path / "tasks.md").exists()
    assert not (tmp_path / "security" / "fail.md").exists()
    assert (tmp_path / "proposal.md").exists()  # not in closure


def test_execute_rollback_archives_with_relative_structure(tmp_path: Path):
    graph = seed_failed_change(tmp_path)
    outcome = read_gate_outcome(tmp_path, graph.node("security").gate.outputs)
    result = execute_rollback(graph, tmp_path, tmp_path, "security", outcome)

    round_dir = tmp_path / ".attempts" / "round-001"
    assert (round_dir / "design.md").exists()
    assert (round_dir / "tasks.md").exists()
    assert (round_dir / "security" / "fail.md").exists()
    assert result.round == 1
    assert set(result.archived) == {"design.md", "tasks.md", "security/fail.md"}


def test_consecutive_rollbacks_increment_round(tmp_path: Path):
    graph = seed_failed_change(tmp_path)
    outcome = read_gate_outcome(tmp_path, graph.node("security").gate.outputs)
    execute_rollback(graph, tmp_path, tmp_path, "security", outcome)

    # simulate a redo that fails again
    (tmp_path / "design.md").write_text("# design v2")
    (tmp_path / "tasks.md").write_text("# tasks v2")
    (tmp_path / "security").mkdir()
    (tmp_path / "security" / "fail.md").write_text("# still blocked")
    outcome2 = read_gate_outcome(tmp_path, graph.node("security").gate.outputs)
    result2 = execute_rollback(graph, tmp_path, tmp_path, "security", outcome2)

    assert result2.round == 2
    assert (tmp_path / ".attempts" / "round-001").exists()
    assert (tmp_path / ".attempts" / "round-002").exists()


def test_meta_yaml_contains_required_fields(tmp_path: Path):
    graph = seed_failed_change(tmp_path)
    outcome = read_gate_outcome(tmp_path, graph.node("security").gate.outputs)
    result = execute_rollback(graph, tmp_path, tmp_path, "security", outcome)

    import yaml

    meta = yaml.safe_load((result.archive_dir / "_meta.yaml").read_text())
    for key in ("round", "gate", "verdict", "reset_closure", "archived_files"):
        assert key in meta


def test_rollback_reruns_state_and_flips_correctly(tmp_path: Path):
    graph = seed_failed_change(tmp_path)
    outcome = read_gate_outcome(tmp_path, graph.node("security").gate.outputs)
    execute_rollback(graph, tmp_path, tmp_path, "security", outcome)

    states = compute_states(graph, tmp_path, tmp_path)
    assert states["design"].status == "ready"
    assert states["tasks"].status == "blocked"
    assert states["security"].status == "blocked"


def test_empty_directory_cleaned_up(tmp_path: Path):
    graph = seed_failed_change(tmp_path)
    outcome = read_gate_outcome(tmp_path, graph.node("security").gate.outputs)
    execute_rollback(graph, tmp_path, tmp_path, "security", outcome)

    assert not (tmp_path / "security").exists()
    assert (tmp_path / ".attempts").exists()


def test_state_md_not_archived(tmp_path: Path):
    graph = seed_failed_change(tmp_path)
    outcome = read_gate_outcome(tmp_path, graph.node("security").gate.outputs)
    execute_rollback(graph, tmp_path, tmp_path, "security", outcome)

    assert (tmp_path / "state.md").exists()
    assert not (tmp_path / ".attempts" / "round-001" / "state.md").exists()


def test_rollback_change_raises_when_no_failed_gate(tmp_path: Path):
    graph = WorkflowGraph(linear_schema_with_gate())
    with pytest.raises(NoFailedGateError):
        rollback_change(graph, tmp_path, tmp_path)


def test_rollback_change_raises_when_exhausted(tmp_path: Path):
    graph = seed_failed_change(tmp_path)
    import yaml

    for i in range(1, 4):
        round_dir = tmp_path / ".attempts" / f"round-{i:03d}"
        round_dir.mkdir(parents=True)
        (round_dir / "_meta.yaml").write_text(yaml.safe_dump({"gate": "security", "round": i}))

    with pytest.raises(RetriesExhaustedError):
        rollback_change(graph, tmp_path, tmp_path)


def test_rollback_change_finds_and_executes(tmp_path: Path):
    graph = seed_failed_change(tmp_path)
    result = rollback_change(graph, tmp_path, tmp_path)
    assert result.gate == "security"
    assert result.rollbacks_used == 1


def test_rollback_one_gate_does_not_affect_unrelated_gate(tmp_path: Path):
    # Two entirely independent chains: a -> gate1, and c -> gate2.
    schema = WorkflowSchema(
        name="sample",
        version=1,
        nodes=[
            make_plain_node("a"),
            make_gate_node("gate1", ["a"], reset=["a"]),
            make_plain_node("c"),
            make_gate_node("gate2", ["c"], reset=["c"]),
        ],
    )
    graph = WorkflowGraph(schema)
    (tmp_path / "a.md").write_text("# a")
    (tmp_path / "gate1").mkdir()
    (tmp_path / "gate1" / "fail.md").write_text("# fail1")
    (tmp_path / "c.md").write_text("# c")
    (tmp_path / "gate2").mkdir()
    (tmp_path / "gate2" / "pass.md").write_text("# pass2")

    result = rollback_change(graph, tmp_path, tmp_path)
    assert result.gate == "gate1"
    assert result.closure == ["a", "gate1"]
    # gate2's independent chain must be untouched
    assert (tmp_path / "c.md").exists()
    assert (tmp_path / "gate2" / "pass.md").exists()
