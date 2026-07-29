from pathlib import Path

import yaml

from loopspec.graph import WorkflowGraph
from loopspec.models import NodeSpec, WorkflowSchema
from loopspec.state import compute_states, count_rollbacks, is_complete


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


def write_meta(round_dir: Path, gate: str) -> None:
    round_dir.mkdir(parents=True)
    (round_dir / "_meta.yaml").write_text(yaml.safe_dump({"gate": gate, "round": 1}))


def test_empty_change_dir_first_node_ready(tmp_path: Path):
    graph = WorkflowGraph(linear_schema_with_gate())
    states = compute_states(graph, tmp_path, tmp_path)
    assert states["proposal"].status == "ready"
    assert states["design"].status == "blocked"
    assert states["tasks"].status == "blocked"
    assert states["security"].status == "blocked"


def test_first_node_done_unlocks_next(tmp_path: Path):
    (tmp_path / "proposal.md").write_text("# p")
    graph = WorkflowGraph(linear_schema_with_gate())
    states = compute_states(graph, tmp_path, tmp_path)
    assert states["proposal"].status == "done"
    assert states["design"].status == "ready"


def test_gate_pass_marks_done_and_advances(tmp_path: Path):
    for name in ("proposal", "design", "tasks"):
        (tmp_path / f"{name}.md").write_text("# x")
    (tmp_path / "security").mkdir()
    (tmp_path / "security" / "pass.md").write_text("# ok")

    graph = WorkflowGraph(linear_schema_with_gate())
    states = compute_states(graph, tmp_path, tmp_path)
    assert states["security"].status == "done"
    assert is_complete(states)


def test_gate_fail_below_max_retries_is_failed(tmp_path: Path):
    for name in ("proposal", "design", "tasks"):
        (tmp_path / f"{name}.md").write_text("# x")
    (tmp_path / "security").mkdir()
    (tmp_path / "security" / "fail.md").write_text("# Blocked\n\n- issue")

    graph = WorkflowGraph(linear_schema_with_gate(max_retries=3))
    states = compute_states(graph, tmp_path, tmp_path)
    assert states["security"].status == "failed"
    assert states["security"].rollbacks_used == 0


def test_gate_fail_at_max_retries_is_exhausted(tmp_path: Path):
    for name in ("proposal", "design", "tasks"):
        (tmp_path / f"{name}.md").write_text("# x")
    (tmp_path / "security").mkdir()
    (tmp_path / "security" / "fail.md").write_text("# Blocked\n\n- issue")
    write_meta(tmp_path / ".attempts" / "round-001", "security")
    write_meta(tmp_path / ".attempts" / "round-002", "security")
    write_meta(tmp_path / ".attempts" / "round-003", "security")

    graph = WorkflowGraph(linear_schema_with_gate(max_retries=3))
    states = compute_states(graph, tmp_path, tmp_path)
    assert states["security"].status == "exhausted"
    assert states["security"].rollbacks_used == 3


def test_max_retries_zero_first_fail_is_exhausted(tmp_path: Path):
    for name in ("proposal", "design", "tasks"):
        (tmp_path / f"{name}.md").write_text("# x")
    (tmp_path / "security").mkdir()
    (tmp_path / "security" / "fail.md").write_text("# Blocked")

    graph = WorkflowGraph(linear_schema_with_gate(max_retries=0))
    states = compute_states(graph, tmp_path, tmp_path)
    assert states["security"].status == "exhausted"


def test_incomplete_round_not_counted(tmp_path: Path):
    (tmp_path / ".attempts" / "round-001").mkdir(parents=True)  # no _meta.yaml
    assert count_rollbacks(tmp_path, "security") == 0


def test_gate_deps_unmet_is_blocked_without_reading_outcome(tmp_path: Path):
    # Even if a stray fail.md exists, unmet deps must short-circuit to blocked.
    (tmp_path / "security").mkdir()
    (tmp_path / "security" / "fail.md").write_text("# stray")

    graph = WorkflowGraph(linear_schema_with_gate())
    states = compute_states(graph, tmp_path, tmp_path)
    assert states["security"].status == "blocked"


def test_multiple_gates_independent(tmp_path: Path):
    schema = WorkflowSchema(
        name="sample",
        version=1,
        nodes=[
            make_plain_node("a"),
            make_gate_node("gate1", ["a"], reset=["a"]),
            make_plain_node("b", ["gate1"]),
            make_gate_node("gate2", ["b"], reset=["b"]),
        ],
    )
    (tmp_path / "a.md").write_text("# a")
    (tmp_path / "gate1").mkdir()
    (tmp_path / "gate1" / "pass.md").write_text("# ok")
    (tmp_path / "b.md").write_text("# b")
    (tmp_path / "gate2").mkdir()
    (tmp_path / "gate2" / "fail.md").write_text("# fail")

    graph = WorkflowGraph(schema)
    states = compute_states(graph, tmp_path, tmp_path)
    assert states["gate1"].status == "done"
    assert states["gate2"].status == "failed"


def test_all_done_is_complete(tmp_path: Path):
    for name in ("proposal", "design", "tasks"):
        (tmp_path / f"{name}.md").write_text("# x")
    (tmp_path / "security").mkdir()
    (tmp_path / "security" / "pass.md").write_text("# ok")

    graph = WorkflowGraph(linear_schema_with_gate())
    states = compute_states(graph, tmp_path, tmp_path)
    assert is_complete(states)


def test_state_md_contents_do_not_affect_status(tmp_path: Path):
    (tmp_path / "state.md").write_text("## Artifact Notes\n- proposal.md: approved\n")
    graph = WorkflowGraph(linear_schema_with_gate())
    states = compute_states(graph, tmp_path, tmp_path)
    # proposal.md itself was never written, so it must stay ready despite the
    # state.md note claiming it's "approved".
    assert states["proposal"].status == "ready"


def tracking_schema(max_retries: int = 3) -> WorkflowSchema:
    apply_node = make_gate_node("apply", ["tasks"], max_retries=max_retries, reset=["tasks"])
    return WorkflowSchema(
        name="sample",
        version=1,
        nodes=[
            make_plain_node("proposal"),
            make_plain_node("tasks", ["proposal"]),
            apply_node.model_copy(update={"tracks": "tasks.md"}),
        ],
    )


def write_tracking_prereqs(root: Path, tasks_body: str | None = "- [x] one\n- [ ] two\n") -> None:
    (root / "proposal.md").write_text("# p")
    if tasks_body is not None:
        (root / "tasks.md").write_text(tasks_body)


def test_tracked_node_not_done_while_tasks_pending(tmp_path: Path):
    write_tracking_prereqs(tmp_path)
    (tmp_path / "apply").mkdir()
    (tmp_path / "apply" / "pass.md").write_text("# report")

    graph = WorkflowGraph(tracking_schema())
    states = compute_states(graph, tmp_path, tmp_path)
    assert states["apply"].status == "ready"
    assert not is_complete(states)


def test_tracked_node_done_when_all_tasks_ticked(tmp_path: Path):
    write_tracking_prereqs(tmp_path, "- [x] one\n- [X] two\n")
    (tmp_path / "apply").mkdir()
    (tmp_path / "apply" / "pass.md").write_text("# report")

    graph = WorkflowGraph(tracking_schema())
    states = compute_states(graph, tmp_path, tmp_path)
    assert states["apply"].status == "done"
    assert is_complete(states)


def test_tracked_node_not_done_when_tracked_file_has_no_tasks(tmp_path: Path):
    write_tracking_prereqs(tmp_path, "## Nothing to do here\n")
    (tmp_path / "apply").mkdir()
    (tmp_path / "apply" / "pass.md").write_text("# report")

    graph = WorkflowGraph(tracking_schema())
    states = compute_states(graph, tmp_path, tmp_path)
    assert states["apply"].status == "ready"


def test_tracked_node_not_done_when_tracked_file_missing(tmp_path: Path):
    # tasks.md absent: `tasks` itself is unfinished, so `apply` stays blocked
    # rather than being declared done off the back of its pass output alone.
    write_tracking_prereqs(tmp_path, tasks_body=None)
    (tmp_path / "apply").mkdir()
    (tmp_path / "apply" / "pass.md").write_text("# report")

    graph = WorkflowGraph(tracking_schema())
    states = compute_states(graph, tmp_path, tmp_path)
    assert states["apply"].status == "blocked"
    assert not is_complete(states)


def test_tracked_node_fail_output_wins_over_task_progress(tmp_path: Path):
    write_tracking_prereqs(tmp_path, "- [x] one\n- [x] two\n")
    (tmp_path / "apply").mkdir()
    (tmp_path / "apply" / "fail.md").write_text("# Blocked\n\n- design is wrong")

    graph = WorkflowGraph(tracking_schema(max_retries=2))
    states = compute_states(graph, tmp_path, tmp_path)
    assert states["apply"].status == "failed"

    write_meta(tmp_path / ".attempts" / "round-001", "apply")
    write_meta(tmp_path / ".attempts" / "round-002", "apply")
    states = compute_states(graph, tmp_path, tmp_path)
    assert states["apply"].status == "exhausted"


def test_untracked_node_done_from_output_alone(tmp_path: Path):
    write_tracking_prereqs(tmp_path)
    (tmp_path / "apply").mkdir()
    (tmp_path / "apply" / "pass.md").write_text("# report")

    # Same fixture, but without `tracks`: the pending checkbox is irrelevant.
    schema = tracking_schema()
    schema.nodes[-1] = schema.nodes[-1].model_copy(update={"tracks": None})
    states = compute_states(WorkflowGraph(schema), tmp_path, tmp_path)
    assert states["apply"].status == "done"


def test_restart_recomputes_same_result(tmp_path: Path):
    for name in ("proposal", "design", "tasks"):
        (tmp_path / f"{name}.md").write_text("# x")
    (tmp_path / "security").mkdir()
    (tmp_path / "security" / "fail.md").write_text("# fail")
    write_meta(tmp_path / ".attempts" / "round-001", "security")

    graph = WorkflowGraph(linear_schema_with_gate(max_retries=3))
    first = compute_states(graph, tmp_path, tmp_path)
    second = compute_states(graph, tmp_path, tmp_path)
    assert first["security"].status == second["security"].status == "failed"
    assert first["security"].rollbacks_used == second["security"].rollbacks_used == 1
