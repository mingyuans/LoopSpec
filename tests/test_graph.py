import pytest

from loopspec.errors import SchemaValidationError
from loopspec.graph import WorkflowGraph, validate_no_cycles
from loopspec.models import NodeSpec, WorkflowSchema


def make_node(node_id: str, requires: list[str] | None = None) -> NodeSpec:
    return NodeSpec(
        id=node_id,
        description=f"node {node_id}",
        generates=f"{node_id}.md",
        template=f"{node_id}.md",
        requires=requires or [],
    )


def make_schema(nodes: list[NodeSpec]) -> WorkflowSchema:
    return WorkflowSchema(name="test-schema", version=1, nodes=nodes)


def test_linear_chain_build_order():
    schema = make_schema(
        [
            make_node("a"),
            make_node("b", ["a"]),
            make_node("c", ["b"]),
        ]
    )
    graph = WorkflowGraph(schema)
    assert graph.build_order() == ["a", "b", "c"]


def test_diamond_dependency_build_order():
    schema = make_schema(
        [
            make_node("a"),
            make_node("c", ["a"]),
            make_node("b", ["a"]),
            make_node("d", ["b", "c"]),
        ]
    )
    graph = WorkflowGraph(schema)
    order = graph.build_order()
    assert order.index("a") < order.index("b")
    assert order.index("a") < order.index("c")
    assert order.index("b") < order.index("d")
    assert order.index("c") < order.index("d")
    # same-tier nodes (b, c) ordered lexicographically
    assert order == ["a", "b", "c", "d"]


def test_ancestors_returns_transitive_dependencies():
    schema = make_schema(
        [
            make_node("a"),
            make_node("b", ["a"]),
            make_node("c", ["b"]),
        ]
    )
    graph = WorkflowGraph(schema)
    assert graph.ancestors("c") == {"a", "b"}
    assert "c" not in graph.ancestors("c")


def test_dependents_returns_direct_successors():
    schema = make_schema(
        [
            make_node("a"),
            make_node("b", ["a"]),
            make_node("c", ["a"]),
            make_node("d", ["b"]),
        ]
    )
    graph = WorkflowGraph(schema)
    assert set(graph.dependents("a")) == {"b", "c"}
    assert graph.dependents("b") == ["d"]


def test_root_node_has_zero_in_degree():
    schema = make_schema([make_node("a"), make_node("b", ["a"])])
    graph = WorkflowGraph(schema)
    assert graph.build_order()[0] == "a"


def test_two_node_cycle_detected():
    nodes = {
        "a": make_node("a", ["b"]),
        "b": make_node("b", ["a"]),
    }
    with pytest.raises(SchemaValidationError) as exc_info:
        validate_no_cycles(nodes)
    assert "a" in str(exc_info.value) and "b" in str(exc_info.value)


def test_three_node_cycle_detected():
    nodes = {
        "a": make_node("a", ["c"]),
        "b": make_node("b", ["a"]),
        "c": make_node("c", ["b"]),
    }
    with pytest.raises(SchemaValidationError):
        validate_no_cycles(nodes)
