"""Deterministic expansion of Fragment nodes; on_fail is pushed down into each Gate."""

from __future__ import annotations

import fnmatch
import re
from dataclasses import dataclass, field

from .errors import WorkflowError
from .models import KEBAB_RE, GateOutputs, GateTemplates
from .workflow_catalog import WorkflowCatalog
from .workflow_io import relative_path
from .workflow_models import FailurePolicy, Node, ResolvedGate, ResolvedNode


@dataclass
class FragmentInstance:
    id: str
    use: str
    parent: str | None = None
    members: list[str] = field(default_factory=list)
    roots: list[str] = field(default_factory=list)
    terminals: list[str] = field(default_factory=list)


@dataclass
class PendingPolicy:
    owner: str
    container: str
    node: Node


class FragmentExpander:
    def __init__(self, catalog: WorkflowCatalog) -> None:
        self.catalog = catalog
        self.leaves: dict[str, Node] = {}
        self.owners: dict[str, str] = {}
        self.instances: dict[str, FragmentInstance] = {}
        self.members: dict[str, list[str]] = {}
        self.policies: list[PendingPolicy] = []
        self.local_nodes: dict[str, dict[str, Node]] = {}
        self.dependencies: dict[str, set[str]] = {}
        self.failures: dict[str, FailurePolicy] = {}

    def expand(
        self, name: str, instance: str, stack: tuple[str, ...] = (), parent: str | None = None
    ) -> list[str]:
        if any(not re.fullmatch(KEBAB_RE, part) for part in instance.split("/")):
            raise WorkflowError("workflow_invalid", "实例路径不合法")
        if name in stack:
            raise WorkflowError("fragment_cycle", "Fragment 递归引用形成环")
        if len(stack) >= 16 or len(self.instances) >= 256:
            raise WorkflowError("resource_limit", "Fragment 展开超过深度或实例限制")
        if instance in self.members or instance in self.instances:
            raise WorkflowError("duplicate_instance", "实例 ID 重复")
        fragment = self.catalog.fragment(name)
        # Reserve the identity first so recursion cannot reuse the name.
        self.instances[instance] = FragmentInstance(id=instance, use=name, parent=parent)
        self.local_nodes[instance] = {node.id: node for node in fragment.nodes}
        collected: list[str] = []
        for node in fragment.nodes:
            identity = instance + "/" + node.id
            if node.use is not None:
                members = self.expand(node.use, identity, (*stack, name), instance)
            else:
                if len(self.leaves) >= 1024:
                    raise WorkflowError("resource_limit", "展开叶子超过数量限制")
                self.leaves[identity] = node.model_copy(deep=True)
                self.owners[identity] = instance
                self.dependencies[identity] = set()
                members = [identity]
            self.members[identity] = members
            collected.extend(members)
            if node.on_fail is not None:
                self.policies.append(PendingPolicy(identity, instance, node))
        self.members[instance] = collected
        self.instances[instance].members = collected
        return collected

    def connect(self) -> dict[str, set[str]]:
        for instance in sorted(self.instances, key=lambda item: (-item.count("/"), item)):
            local = self.local_nodes[instance]
            for node in local.values():
                identity = instance + "/" + node.id
                roots = self.instances[identity].roots if node.use else [identity]
                for dependency in node.requires:
                    if dependency not in local:
                        raise WorkflowError("missing_dependency", "requires 引用不存在的兄弟节点")
                    source = instance + "/" + dependency
                    terminals = (
                        self.instances[source].terminals if local[dependency].use else [source]
                    )
                    for target in roots:
                        self.dependencies[target].update(terminals)
            self.refresh(instance)
        return self.dependencies

    def refresh(self, instance: str) -> None:
        members = set(self.instances[instance].members)
        internal_predecessors = set().union(*(self.dependencies[n] & members for n in members))
        self.instances[instance].roots = sorted(
            n for n in members if not self.dependencies[n] & members
        )
        self.instances[instance].terminals = sorted(members - internal_predecessors)

    def assign(self, owner: str, targets: set[str], max_retries: int) -> None:
        """Push one on_fail down to every Gate under `owner`; a Gate takes at most one."""
        roots = self.instances[owner].roots if owner in self.instances else [owner]
        if not roots or any(not targets <= ancestors(self.dependencies, root) for root in roots):
            raise WorkflowError("invalid_reset", "reset 目标必须是失败范围的执行祖先")
        sources = sorted(n for n in self.members[owner] if self.leaves[n].gate)
        if not sources:
            raise WorkflowError("invalid_reset", "on_fail 所在范围没有实际 Gate")
        for source in sources:
            if source in self.failures:
                raise WorkflowError("on_fail_conflict", "同一 Gate 收到多条 on_fail，请只保留一条")
            self.failures[source] = FailurePolicy(reset=sorted(targets), max_retries=max_retries)

    def validate(self) -> None:
        build_order(self.dependencies)
        for pending in self.policies:
            policy = pending.node.on_fail
            assert policy is not None
            targets: set[str] = set()
            for target in policy.reset:
                if target not in self.local_nodes[pending.container]:
                    raise WorkflowError("invalid_reset", "reset 必须引用同容器的上游节点")
                targets.update(self.members[pending.container + "/" + target])
            self.assign(pending.owner, targets, policy.max_retries)
        for identity, node in self.leaves.items():
            if node.tracks is None:
                continue
            candidates = [
                n
                for n in ancestors(self.dependencies, identity)
                if self.owners[n] == self.owners[identity]
                and self.leaves[n].generates == node.tracks
            ]
            if not candidates:
                raise WorkflowError("invalid_tracks", "任务跟踪文件必须由上游节点生成")

    def resolve_nodes(self) -> list[ResolvedNode]:
        results: list[ResolvedNode] = []
        claimed: list[str] = []

        def output(owner: str, value: str, glob: bool = False) -> str:
            value = relative_path(value, glob=glob)
            if any(
                p in {".gates", ".gate-rounds", ".attempts", "plan.yaml", "state.md"}
                for p in value.split("/")
            ):
                raise WorkflowError("unsafe_output", "产物不能进入控制目录")
            path = "artifacts/" + owner + "/" + value
            if any(patterns_overlap(path, old) for old in claimed):
                raise WorkflowError("output_conflict", "产物路径存在重复或模糊重叠")
            claimed.append(path)
            return path

        for identity in build_order(self.dependencies):
            node = self.leaves[identity]
            owner = self.owners[identity]
            source = self.instances[owner].use
            gate = (
                ResolvedGate(
                    outputs=node.gate.outputs,
                    templates=node.gate.templates,
                    evidence=node.gate.evidence,
                    assurance=node.gate.assurance,
                    on_fail=self.failures.get(identity),
                )
                if node.gate
                else None
            )
            if gate:
                gate.outputs = GateOutputs.model_validate(
                    {
                        "pass": output(owner, gate.outputs.pass_),
                        "fail": output(owner, gate.outputs.fail),
                    }
                )
                if gate.templates:
                    gate.templates = GateTemplates.model_validate(
                        {
                            "pass": self.catalog.resource(source, gate.templates.pass_),
                            "fail": self.catalog.resource(source, gate.templates.fail),
                        }
                    )
                if gate.evidence:
                    for pattern in gate.evidence.paths:
                        relative_path(pattern, glob=True)
                    if any(not re.fullmatch(KEBAB_RE, name) for name in gate.evidence.provides):
                        raise WorkflowError("workflow_invalid", "审查能力名称不合法")
                if gate.assurance:
                    gate.assurance = self.catalog.resource(source, gate.assurance)
            results.append(
                ResolvedNode(
                    id=identity,
                    fragment=owner,
                    description=node.description or None,
                    requires=sorted(self.dependencies[identity]),
                    gate=gate,
                    generates=output(owner, node.generates, glob=True) if node.generates else None,
                    instruction=self.catalog.resource(source, node.instruction)
                    if node.instruction
                    else None,
                    template=self.catalog.resource(source, node.template)
                    if node.template
                    else None,
                    tracks=(
                        "artifacts/" + owner + "/" + relative_path(node.tracks)
                        if node.tracks
                        else None
                    ),
                )
            )
        return results


def patterns_overlap(first: str, second: str) -> bool:
    if fnmatch.fnmatchcase(first, second) or fnmatch.fnmatchcase(second, first):
        return True
    if not any(c in first + second for c in "*?["):
        return first.startswith(second + "/") or second.startswith(first + "/")
    anchor_first = re.split(r"[*?\[]", first, maxsplit=1)[0]
    anchor_second = re.split(r"[*?\[]", second, maxsplit=1)[0]
    return anchor_first.startswith(anchor_second) or anchor_second.startswith(anchor_first)


def build_order(dependencies: dict[str, set[str]]) -> list[str]:
    if any(not deps <= dependencies.keys() for deps in dependencies.values()):
        raise WorkflowError("missing_dependency", "展开图含不存在的依赖")
    remaining = {key: set(value) for key, value in dependencies.items()}
    order: list[str] = []
    while remaining:
        ready = sorted(key for key, deps in remaining.items() if not deps)
        if not ready:
            raise WorkflowError("dependency_cycle", "执行依赖形成环")
        current = ready[0]
        order.append(current)
        del remaining[current]
        for deps in remaining.values():
            deps.discard(current)
    return order


def ancestors(dependencies: dict[str, set[str]], node: str) -> set[str]:
    result: set[str] = set()
    pending = list(dependencies[node])
    while pending:
        current = pending.pop()
        if current not in result:
            result.add(current)
            pending.extend(dependencies[current])
    return result
