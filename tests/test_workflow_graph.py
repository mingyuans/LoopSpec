"""Unit tests for `loopspec graph`: layering, rendering safety and the browser decision."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from loopspec.errors import WorkflowError
from loopspec.workflow_graph import (
    browser_decision,
    from_resolved,
    open_in_browser,
    plan_graph,
    profile_graph,
    write_graph,
)
from loopspec.workflow_graph_html import NODE_H, NODE_W, layout, render_html
from loopspec.workflow_models import FragmentRef, ResolvedNode
from tests.workflow_helpers import (
    BUGFIX_FLOW,
    create_approved,
    create_draft,
    invoke,
    new_change,
    project,
)


def leaf(identity: str, requires: tuple[str, ...] = (), description: str | None = None):
    return ResolvedNode(
        id=identity,
        fragment=identity.rsplit("/", 1)[0],
        requires=list(requires),
        generates=f"artifacts/{identity}.md",
        description=description,
    )


@pytest.fixture
def home(tmp_path: Path) -> Path:
    return project(tmp_path)


def test_large_feature_runs_frontend_and_backend_in_parallel(home: Path) -> None:
    graph = profile_graph(home, "large-feature")
    fe_first = graph.nodes["fe/code/implement"]
    be_first = graph.nodes["be/code/implement"]
    assert fe_first.layer == be_first.layer
    assert fe_first.layer + 1 in graph.parallel_layers
    assert graph.nodes["requirements/proposal"].layer == 0


def test_nodes_of_one_layer_never_depend_on_each_other(home: Path) -> None:
    graph = profile_graph(home, "large-feature")
    for layer in graph.layers:
        members = set(layer)
        for identity in layer:
            assert not members & set(graph.nodes[identity].requires)
    for source, target in graph.edges:
        assert graph.nodes[source].layer < graph.nodes[target].layer


def test_every_leaf_appears_exactly_once_in_the_layers(home: Path) -> None:
    graph = profile_graph(home, "large-feature")
    flat = [identity for layer in graph.layers for identity in layer]
    assert sorted(flat) == sorted(graph.nodes)


def test_on_fail_becomes_a_rework_edge_with_its_retry_budget(home: Path) -> None:
    graph = profile_graph(home, "bugfix")
    qa = next(edge for edge in graph.fail_edges if edge.gate == "qa/test")
    assert "be/code/implement" in qa.targets
    assert qa.max_retries == 3
    html = render_html(graph)
    assert 'class="fail" data-from="qa/test" data-to="be/code/implement"' in html
    assert "on_fail ×3" in html


def test_a_flow_without_on_fail_draws_no_rework_edge() -> None:
    nodes = [leaf("a/x"), leaf("b/y", ("a/x",))]
    flow = [FragmentRef(id="a", use="design"), FragmentRef(id="b", use="design", requires=["a"])]
    graph = from_resolved(kind="profile", title="t", subtitle="", nodes=nodes, flow=flow)
    assert graph.fail_edges == []
    assert 'class="fail"' not in render_html(graph)
    assert graph.parallel_layers == []


def test_node_kinds_follow_the_gate_type(home: Path) -> None:
    graph = profile_graph(home, "bugfix")
    assert graph.nodes["requirements/proposal"].kind == "artifact"
    assert graph.nodes["be/tests/check"].kind == "code-gate"
    assert graph.nodes["qa/test"].kind == "gate"
    assert graph.nodes["assurance/check"].kind == "assurance"


def test_rendering_is_deterministic(home: Path) -> None:
    first = render_html(profile_graph(home, "large-feature"))
    second = render_html(profile_graph(home, "large-feature"))
    assert first == second


def test_untrusted_text_is_escaped_and_cannot_close_the_script() -> None:
    hostile = '</script><script>alert(1)</script><img src=x onerror="y">'
    nodes = [leaf("a/x", description=hostile)]
    graph = from_resolved(
        kind="plan",
        title="<b>title</b>",
        subtitle=hostile,
        nodes=nodes,
        flow=[FragmentRef(id="a", use="design")],
        meta={"Note": hostile},
    )
    html = render_html(graph)
    assert "<script>alert(1)" not in html
    assert "<img" not in html
    assert "<b>title</b>" not in html
    # Exactly the page's own two script elements.
    assert html.count("</script>") == 2


def test_page_loads_no_external_resource(home: Path) -> None:
    html = render_html(profile_graph(home, "large-feature"))
    assert "http://" not in html and "https://" not in html
    assert not re.search(r"<(script|link|img|iframe)[^>]+(src|href)=", html)
    assert "@import" not in html


def test_draft_plan_shows_digest_without_runtime_status(home: Path) -> None:
    new_change(home)
    draft = create_draft(home, BUGFIX_FLOW)
    graph = plan_graph(home, "AFD1111", None)
    assert graph.meta["Status"] == "draft"
    assert graph.meta["Digest"] == draft["digest"]
    assert all(node.status is None for node in graph.nodes.values())


def test_active_plan_overlays_leaf_status(home: Path) -> None:
    create_approved(home, BUGFIX_FLOW)
    graph = plan_graph(home, "AFD1111", "001")
    assert graph.nodes["requirements/proposal"].status == "ready"
    assert graph.nodes["be/code/implement"].status == "blocked"
    assert "status-ready" in render_html(graph)


def test_plan_without_an_open_plan_is_reported(home: Path) -> None:
    new_change(home)
    with pytest.raises(WorkflowError) as caught:
        plan_graph(home, "AFD1111", None)
    assert caught.value.code == "plan_not_found"


@pytest.mark.parametrize(
    ("no_open", "env", "platform", "expected"),
    [
        (True, {"DISPLAY": ":0"}, "linux", (False, "--no-open")),
        (
            False,
            {"SSH_CONNECTION": "1 2 3 4", "DISPLAY": ":0"},
            "linux",
            (False, "remote session (SSH)"),
        ),
        (False, {"SSH_TTY": "/dev/pts/1"}, "darwin", (False, "remote session (SSH)")),
        (False, {}, "linux", (False, "no graphical display")),
        (False, {"WAYLAND_DISPLAY": "wayland-0"}, "linux", (True, None)),
        (False, {}, "darwin", (True, None)),
        (False, {}, "win32", (True, None)),
    ],
)
def test_browser_decision(no_open: bool, env: dict, platform: str, expected: tuple) -> None:
    assert browser_decision(no_open, env, platform) == expected


def test_a_failing_browser_only_means_printing_the_link() -> None:
    def broken(url: str) -> bool:
        raise RuntimeError("no browser")

    assert open_in_browser("file:///x.html", broken) == (False, "no browser available")
    assert open_in_browser("file:///x.html", lambda url: False) == (False, "no browser available")
    assert open_in_browser("file:///x.html", lambda url: True) == (True, None)


def test_default_output_lives_in_the_home_cache(home: Path) -> None:
    path = write_graph(home, "<html></html>", ".cache/graph/profile-x.html", None)
    assert path == (home / ".cache/graph/profile-x.html").resolve()
    assert path.read_text() == "<html></html>"


def test_explicit_output_creates_parent_directories(tmp_path: Path, home: Path) -> None:
    target = tmp_path / "out" / "nested" / "g.html"
    assert write_graph(home, "x", "ignored", target) == target.resolve()
    assert target.read_text() == "x"


def test_output_that_is_a_directory_is_rejected(tmp_path: Path, home: Path) -> None:
    with pytest.raises(WorkflowError) as caught:
        write_graph(home, "x", "ignored", tmp_path)
    assert caught.value.code == "output_invalid"


def test_archived_plan_can_be_drawn_without_status(home: Path) -> None:
    new_change(home)
    create_draft(home, BUGFIX_FLOW)
    code, result = invoke(home, "plan", "archive", "-c", "AFD1111", "-p", "001")
    assert code == 0, result
    graph = plan_graph(home, "AFD1111", "001")
    assert graph.meta["Status"] == "archived"
    assert all(node.status is None for node in graph.nodes.values())


def test_malformed_plan_number_is_rejected(home: Path) -> None:
    new_change(home)
    with pytest.raises(WorkflowError) as caught:
        plan_graph(home, "AFD1111", "1")
    assert caught.value.code == "invalid_plan"


@pytest.mark.parametrize("name", ["large-feature", "bugfix", "frontend-small-change"])
def test_instance_boxes_never_overlap(home: Path, name: str) -> None:
    graph = profile_graph(home, name)
    positions, _, _ = layout(graph)
    boxes = {}
    for instance in graph.instances:
        if "/" in instance.id:
            continue
        xs = [positions[m][0] for m in instance.members]
        ys = [positions[m][1] for m in instance.members]
        boxes[instance.id] = (min(xs), min(ys), max(xs) + NODE_W, max(ys) + NODE_H)
    names = sorted(boxes)
    for index, first in enumerate(names):
        for second in names[index + 1 :]:
            a, b = boxes[first], boxes[second]
            overlap = a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]
            assert not overlap, (first, second)
    # Nodes never sit on top of each other either.
    assert len(set(positions.values())) == len(positions)
