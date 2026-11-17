"""`loopspec graph`: a Profile or Plan as a layered dependency graph in a standalone HTML page.

The graph is built from resolved leaf nodes, so a Profile (compiled on the fly) and a Plan
(already compiled in `spec.nodes`) share one path. Layers are longest-path layers: every
dependency strictly raises the layer, so the nodes of one layer never depend on each other
and may run in parallel.
"""

from __future__ import annotations

import os
import sys
import uuid
import webbrowser
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path

from .errors import WorkflowError
from .workflow_compiler import build_order
from .workflow_io import atomic_write
from .workflow_models import FragmentRef, ResolvedNode

GRAPH_DIR = ".cache/graph"
SSH_REASON = "remote session (SSH)"
HEADLESS_REASON = "no graphical display"
#: Reasons that mean the user sits elsewhere and has to copy the file to see it.
REMOTE_REASONS = (SSH_REASON, HEADLESS_REASON)
#: Barycenter passes that reorder each layer to reduce edge crossings; bounded for big Plans.
ORDER_PASSES = 4


@dataclass(frozen=True)
class GraphNode:
    id: str
    instance: str
    kind: str  # artifact | gate | code-gate | assurance
    layer: int
    output: str | None = None
    description: str | None = None
    status: str | None = None
    requires: tuple[str, ...] = ()


@dataclass(frozen=True)
class FailEdge:
    gate: str
    targets: tuple[str, ...]
    max_retries: int


@dataclass(frozen=True)
class GraphInstance:
    id: str
    use: str | None
    members: tuple[str, ...]


@dataclass
class WorkflowGraph:
    kind: str  # profile | plan
    title: str
    subtitle: str
    meta: dict[str, str] = field(default_factory=dict)
    nodes: dict[str, GraphNode] = field(default_factory=dict)
    edges: list[tuple[str, str]] = field(default_factory=list)
    fail_edges: list[FailEdge] = field(default_factory=list)
    instances: list[GraphInstance] = field(default_factory=list)
    layers: list[list[str]] = field(default_factory=list)

    @property
    def parallel_layers(self) -> list[int]:
        """1-based numbers of the layers holding two or more independent nodes."""
        return [index + 1 for index, layer in enumerate(self.layers) if len(layer) > 1]


def node_kind(node: ResolvedNode) -> str:
    if node.gate is None:
        return "artifact"
    if node.gate.assurance:
        return "assurance"
    if node.gate.evidence:
        return "code-gate"
    return "gate"


def node_output(node: ResolvedNode) -> str | None:
    if node.gate is not None:
        return f"{node.gate.outputs.pass_} | {node.gate.outputs.fail}"
    return node.generates


def layer_of(dependencies: dict[str, set[str]]) -> dict[str, int]:
    layers: dict[str, int] = {}
    for identity in build_order(dependencies):
        layers[identity] = 1 + max((layers[dep] for dep in dependencies[identity]), default=-1)
    return layers


def order_layers(
    layers: dict[str, int], dependencies: dict[str, set[str]], initial: list[str]
) -> list[list[str]]:
    """Group by layer, then reorder each layer by the mean position of its neighbours."""
    count = 1 + max(layers.values(), default=-1)
    rows: list[list[str]] = [[] for _ in range(count)]
    for identity in initial:
        rows[layers[identity]].append(identity)
    successors: dict[str, set[str]] = {identity: set() for identity in dependencies}
    for identity, deps in dependencies.items():
        for dep in deps:
            successors[dep].add(identity)

    def reorder(row: list[str], neighbours: dict[str, set[str]], index: dict[str, int]) -> None:
        # list.sort empties the list while sorting, so positions are captured first.
        current = {identity: position for position, identity in enumerate(row)}

        def key(identity: str) -> tuple[float, int, str]:
            around = [index[n] for n in neighbours[identity] if n in index]
            centre = sum(around) / len(around) if around else float(current[identity])
            return (centre, current[identity], identity)

        row.sort(key=key)

    for sweep in range(ORDER_PASSES):
        downward = sweep % 2 == 0
        sequence = range(1, count) if downward else range(count - 2, -1, -1)
        for number in sequence:
            neighbour_row = rows[number - 1] if downward else rows[number + 1]
            index = {identity: position for position, identity in enumerate(neighbour_row)}
            reorder(rows[number], dependencies if downward else successors, index)
    return rows


def instance_groups(nodes: list[ResolvedNode], flow: list[FragmentRef]) -> list[GraphInstance]:
    """Top-level flow instances and nested reference instances, derived from leaf paths."""
    uses = {ref.id: ref.use for ref in flow}
    prefixes: list[str] = []
    for node in nodes:
        parts = node.fragment.split("/")
        for depth in range(1, len(parts) + 1):
            prefix = "/".join(parts[:depth])
            if prefix not in prefixes:
                prefixes.append(prefix)
    return [
        GraphInstance(
            id=prefix,
            use=uses.get(prefix),
            members=tuple(n.id for n in nodes if n.id.startswith(prefix + "/")),
        )
        for prefix in prefixes
    ]


def from_resolved(
    *,
    kind: str,
    title: str,
    subtitle: str,
    nodes: list[ResolvedNode],
    flow: list[FragmentRef],
    meta: Mapping[str, str] | None = None,
    statuses: Mapping[str, str] | None = None,
) -> WorkflowGraph:
    dependencies = {node.id: set(node.requires) for node in nodes}
    layers = layer_of(dependencies)
    graph = WorkflowGraph(kind=kind, title=title, subtitle=subtitle, meta=dict(meta or {}))
    for node in nodes:
        graph.nodes[node.id] = GraphNode(
            id=node.id,
            instance=node.fragment,
            kind=node_kind(node),
            layer=layers[node.id],
            output=node_output(node),
            description=node.description,
            status=(statuses or {}).get(node.id),
            requires=tuple(sorted(node.requires)),
        )
        graph.edges.extend((dep, node.id) for dep in sorted(node.requires))
        if node.gate is not None and node.gate.on_fail is not None:
            policy = node.gate.on_fail
            graph.fail_edges.append(
                FailEdge(node.id, tuple(sorted(policy.reset)), policy.max_retries)
            )
    graph.layers = order_layers(layers, dependencies, [node.id for node in nodes])
    graph.instances = instance_groups(nodes, flow)
    return graph


# ---------------------------------------------------------------------------- sources


def profile_graph(home: Path, name: str) -> WorkflowGraph:
    from .workflow_catalog import WorkflowCatalog
    from .workflow_planning import compile_flow

    catalog = WorkflowCatalog(home)
    profile = catalog.profile(name)
    nodes = compile_flow(catalog, profile.flow).resolve_nodes()
    meta = {"Profile": profile.name}
    if profile.description:
        meta["Description"] = profile.description
    return from_resolved(
        kind="profile",
        title=f"Profile {profile.name}",
        subtitle=profile.description,
        nodes=nodes,
        flow=profile.flow,
        meta=meta,
    )


def plan_graph(home: Path, change: str, plan_id: str | None) -> WorkflowGraph:
    from .workflow_runtime import status
    from .workflow_state import LoadedPlan, check_plan_id, open_change, read_plan

    ctx = open_change(home, change)
    selected = check_plan_id(plan_id) if plan_id else ctx.open_plan()
    if selected is None:
        raise WorkflowError(
            "plan_not_found", "没有未结束的 Plan", f"用 plan list -c {change} 查看历史 Plan。"
        )
    document = read_plan(ctx.root, selected)
    statuses: dict[str, str] | None = None
    if ctx.active_plan() == selected:
        report = status(LoadedPlan(ctx, selected, document))
        statuses = {entry["id"]: entry["status"] for entry in report["nodes"]}
    meta = {
        "Change": change,
        "Plan": selected,
        "Status": document.meta.status,
        "Revision": str(document.meta.revision),
        "Digest": document.meta.digest,
    }
    if document.spec.based_on:
        meta["Based on"] = document.spec.based_on
    if document.meta.note:
        meta["Note"] = document.meta.note
    return from_resolved(
        kind="plan",
        title=f"{change} / Plan {selected}",
        subtitle=document.meta.note or "",
        nodes=document.spec.nodes,
        flow=document.spec.flow,
        meta=meta,
        statuses=statuses,
    )


# ------------------------------------------------------------------------ output


def default_output(kind: str, change: str | None, plan: str | None, profile: str | None) -> str:
    if kind == "profile":
        return f"{GRAPH_DIR}/profile-{profile}.html"
    return f"{GRAPH_DIR}/plan-{change}-{plan}.html"


def write_graph(home: Path, html: str, relative: str, output: Path | None) -> Path:
    """Write under `<home>/.cache/graph/` by default, or exactly where `--output` says."""
    data = html.encode("utf-8")
    if output is None:
        atomic_write(home, relative, data)
        return (home / relative).resolve()
    target = output.expanduser()
    if target.is_dir():
        raise WorkflowError("output_invalid", "--output 指向一个目录", "传入 HTML 文件路径。")
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        # Write a sibling temporary file and rename it, so a reader never sees half a page
        # and an existing symlink at the target is replaced rather than followed.
        temporary = target.with_name(f".{target.name}.{uuid.uuid4().hex}.tmp")
        try:
            temporary.write_bytes(data)
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)
    except OSError as exc:
        raise WorkflowError(
            "output_invalid", "无法写入 --output 指定的文件", "检查路径与写权限。"
        ) from exc
    return target.resolve()


def browser_decision(
    no_open: bool, env: Mapping[str, str] | None = None, platform: str | None = None
) -> tuple[bool, str | None]:
    """Whether to try a browser at all; remote and headless sessions only get the link."""
    env = os.environ if env is None else env
    platform = sys.platform if platform is None else platform
    if no_open:
        return False, "--no-open"
    if env.get("SSH_CONNECTION") or env.get("SSH_TTY"):
        return False, SSH_REASON
    if platform.startswith("linux") and not (env.get("DISPLAY") or env.get("WAYLAND_DISPLAY")):
        return False, HEADLESS_REASON
    return True, None


def open_in_browser(
    url: str, opener: Callable[[str], bool] | None = None
) -> tuple[bool, str | None]:
    try:
        opened = bool((opener or webbrowser.open)(url))
    except Exception:  # noqa: BLE001 - any browser failure only means "print the link"
        opened = False
    return (True, None) if opened else (False, "no browser available")
