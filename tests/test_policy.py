from pathlib import Path

import pytest

from loopspec.graph import WorkflowGraph
from loopspec.models import NodeSpec, WorkflowSchema
from loopspec.policy import build_next_steps
from loopspec.state import compute_states


def make_gate_node(
    node_id: str, requires: list[str], reset: list[str], max_retries: int = 3
) -> NodeSpec:
    return NodeSpec(
        id=node_id,
        description=node_id,
        generates=None,
        template=None,
        requires=requires,
        gate={
            "outputs": {"pass": f"{node_id}/pass.md", "fail": f"{node_id}/fail.md"},
            "templates": {"pass": "pass.md", "fail": "fail.md"},
            "on_fail": {"reset": reset, "max_retries": max_retries},
        },
    )


def make_plain_node(node_id: str, requires: list[str] | None = None) -> NodeSpec:
    return NodeSpec(
        id=node_id, description=node_id, generates=f"{node_id}.md", template=f"{node_id}.md",
        requires=requires or [],
    )


def linear_schema(max_retries: int = 3) -> WorkflowSchema:
    return WorkflowSchema(
        name="sample",
        version=1,
        nodes=[
            make_plain_node("proposal"),
            make_plain_node("design", ["proposal"]),
            make_gate_node("security", ["design"], reset=["design"], max_retries=max_retries),
        ],
    )


def test_failed_gate_takes_priority_over_unrelated_ready_node(tmp_path: Path):
    # A sibling branch ("docs") that is independent of the design/security chain
    # can be `ready` at the same time security is `failed`; the failed gate must
    # still win so the LLM doesn't skip straight to generating an unrelated node.
    schema = WorkflowSchema(
        name="sample",
        version=1,
        nodes=[
            make_plain_node("proposal"),
            make_plain_node("design", ["proposal"]),
            make_gate_node("security", ["design"], reset=["design"]),
            make_plain_node("docs", ["proposal"]),
        ],
    )
    graph = WorkflowGraph(schema)
    (tmp_path / "proposal.md").write_text("# p")
    (tmp_path / "design.md").write_text("# d")
    (tmp_path / "security").mkdir()
    (tmp_path / "security" / "fail.md").write_text("# Blocked\n\n- issue")

    states = compute_states(graph, tmp_path, tmp_path)
    assert states["docs"].status == "ready"
    assert states["security"].status == "failed"

    steps = build_next_steps("my-change", graph, states)
    assert "rollback" in steps[1]
    assert "security" in steps[0]


def test_ready_node_returns_instructions_command(tmp_path: Path):
    graph = WorkflowGraph(linear_schema())
    states = compute_states(graph, tmp_path, tmp_path)
    steps = build_next_steps("my-change", graph, states)
    assert "instructions proposal" in steps[0]
    assert "--change my-change" in steps[0]


@pytest.mark.parametrize("scenario", ["ready", "failed", "exhausted"])
def test_next_steps_commands_never_quote_the_change_name(tmp_path: Path, scenario: str):
    """Emitted commands must survive being run literally, without shell quote-stripping.

    Change names are kebab-case-only, so quoting buys nothing and breaks callers
    that pass the command through without shell interpretation.
    """
    import yaml

    max_retries = 1 if scenario == "exhausted" else 3
    graph = WorkflowGraph(linear_schema(max_retries=max_retries))

    if scenario in ("failed", "exhausted"):
        (tmp_path / "proposal.md").write_text("# p")
        (tmp_path / "design.md").write_text("# d")
        (tmp_path / "security").mkdir()
        (tmp_path / "security" / "fail.md").write_text("# Blocked\n\n- issue")
    if scenario == "exhausted":
        round_dir = tmp_path / ".attempts" / "round-001"
        round_dir.mkdir(parents=True)
        (round_dir / "_meta.yaml").write_text(yaml.safe_dump({"gate": "security", "round": 1}))

    states = compute_states(graph, tmp_path, tmp_path)
    steps = build_next_steps("my-change", graph, states)

    for step in steps:
        assert '"my-change"' not in step
        assert "'my-change'" not in step


def test_exhausted_gate_returns_escalation(tmp_path: Path):
    import yaml

    graph = WorkflowGraph(linear_schema(max_retries=1))
    (tmp_path / "proposal.md").write_text("# p")
    (tmp_path / "design.md").write_text("# d")
    (tmp_path / "security").mkdir()
    (tmp_path / "security" / "fail.md").write_text("# Blocked")
    round_dir = tmp_path / ".attempts" / "round-001"
    round_dir.mkdir(parents=True)
    (round_dir / "_meta.yaml").write_text(yaml.safe_dump({"gate": "security", "round": 1}))

    states = compute_states(graph, tmp_path, tmp_path)
    assert states["security"].status == "exhausted"

    steps = build_next_steps("my-change", graph, states)
    assert "history" in steps[1]


def test_all_done_returns_completion_message(tmp_path: Path):
    graph = WorkflowGraph(linear_schema())
    (tmp_path / "proposal.md").write_text("# p")
    (tmp_path / "design.md").write_text("# d")
    (tmp_path / "security").mkdir()
    (tmp_path / "security" / "pass.md").write_text("# ok")

    states = compute_states(graph, tmp_path, tmp_path)
    steps = build_next_steps("my-change", graph, states)
    assert steps == ["All nodes are complete."]


def test_multiple_failed_gates_returns_only_earliest(tmp_path: Path):
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
    graph = WorkflowGraph(schema)
    (tmp_path / "a.md").write_text("# a")
    (tmp_path / "gate1").mkdir()
    (tmp_path / "gate1" / "fail.md").write_text("# fail1")
    (tmp_path / "b.md").write_text("# b")
    (tmp_path / "gate2").mkdir()
    (tmp_path / "gate2" / "fail.md").write_text("# fail2")

    states = compute_states(graph, tmp_path, tmp_path)
    steps = build_next_steps("my-change", graph, states)
    assert "gate1" in steps[0]
    assert "gate2" not in steps[0]
