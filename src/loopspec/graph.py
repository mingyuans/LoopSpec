"""Dependency graph algorithms: cycle detection, topological sort, ancestors/dependents."""

from __future__ import annotations

from .errors import SchemaValidationError
from .models import NodeSpec, WorkflowSchema

_WHITE, _GRAY, _BLACK = 0, 1, 2


def validate_no_cycles(nodes: dict[str, NodeSpec]) -> None:
    """Raise SchemaValidationError if `requires` relationships form a cycle."""

    color = {node_id: _WHITE for node_id in nodes}
    parent: dict[str, str] = {}

    def dfs(node_id: str) -> list[str] | None:
        color[node_id] = _GRAY
        for dep in nodes[node_id].requires:
            if color[dep] == _WHITE:
                parent[dep] = node_id
                cycle = dfs(dep)
                if cycle:
                    return cycle
            elif color[dep] == _GRAY:
                path = [dep]
                cur = node_id
                while cur != dep:
                    path.insert(0, cur)
                    cur = parent[cur]
                path.insert(0, dep)
                return path
        color[node_id] = _BLACK
        return None

    for node_id in sorted(nodes):
        if color[node_id] == _WHITE:
            cycle = dfs(node_id)
            if cycle:
                raise SchemaValidationError(
                    f"Cyclic dependency: {' → '.join(cycle)}",
                    fix="Remove the circular `requires` reference between these nodes.",
                )


class WorkflowGraph:
    """Dependency graph built from a WorkflowSchema's nodes."""

    def __init__(self, schema: WorkflowSchema) -> None:
        self._nodes: dict[str, NodeSpec] = {node.id: node for node in schema.nodes}
        validate_no_cycles(self._nodes)
        self._dependents: dict[str, list[str]] = {node_id: [] for node_id in self._nodes}
        for node_id, node in self._nodes.items():
            for dep in node.requires:
                self._dependents[dep].append(node_id)

    def node(self, node_id: str) -> NodeSpec:
        return self._nodes[node_id]

    def node_ids(self) -> list[str]:
        return list(self._nodes)

    def build_order(self) -> list[str]:
        """Kahn's algorithm topological sort; same-tier nodes ordered lexicographically."""

        in_degree = {node_id: len(node.requires) for node_id, node in self._nodes.items()}
        queue = sorted(node_id for node_id, degree in in_degree.items() if degree == 0)
        order: list[str] = []
        while queue:
            current = queue.pop(0)
            order.append(current)
            newly_ready = []
            for dep in self._dependents[current]:
                in_degree[dep] -= 1
                if in_degree[dep] == 0:
                    newly_ready.append(dep)
            queue.extend(sorted(newly_ready))
            queue.sort()
        return order

    def ancestors(self, node_id: str) -> set[str]:
        """All transitive dependencies of `node_id`, excluding itself."""

        result: set[str] = set()
        stack = list(self._nodes[node_id].requires)
        while stack:
            current = stack.pop()
            if current in result:
                continue
            result.add(current)
            stack.extend(self._nodes[current].requires)
        return result

    def dependents(self, node_id: str) -> list[str]:
        """Direct successors of `node_id`."""

        return list(self._dependents[node_id])
