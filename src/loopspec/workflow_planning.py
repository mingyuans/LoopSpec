"""Compile a Plan request into a confirmable spec; project constraints are read live."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from .errors import WorkflowError
from .models import KEBAB_RE, WorkflowConfig
from .workflow_catalog import WorkflowCatalog
from .workflow_compiler import FragmentExpander, ancestors, build_order
from .workflow_io import ResourceBundle, digest, relative_path
from .workflow_models import (
    AssuranceRule,
    AssuranceRules,
    FragmentRef,
    PlanRequest,
    PlanSpec,
    Profile,
    ProjectWorkflow,
    ResolvedNode,
)


def compile_flow(catalog: WorkflowCatalog, flow: list[FragmentRef]) -> FragmentExpander:
    names = {entry.id for entry in flow}
    if len(names) != len(flow):
        raise WorkflowError("duplicate_instance", "flow 实例 ID 必须唯一")
    expander = FragmentExpander(catalog)
    for entry in flow:
        expander.expand(entry.use, entry.id)
    expander.connect()
    for entry in flow:
        if len(entry.requires) != len(set(entry.requires)) or not set(entry.requires) <= names:
            raise WorkflowError("missing_dependency", "flow 依赖必须唯一且指向既有实例")
        for predecessor in entry.requires:
            for root in expander.instances[entry.id].roots:
                expander.dependencies[root].update(expander.instances[predecessor].terminals)
    build_order(expander.dependencies)
    expander.validate()
    for entry in flow:
        if entry.on_fail is None:
            continue
        targets: set[str] = set()
        for target in entry.on_fail.reset:
            if target not in names or target == entry.id:
                raise WorkflowError("invalid_reset", "flow on_fail 必须指向同一 flow 中的上游实例")
            targets.update(expander.instances[target].members)
        expander.assign(entry.id, targets, entry.on_fail.max_retries)
    return expander


def validate_profile(catalog: WorkflowCatalog, profile: Profile) -> dict:
    expanded = compile_flow(catalog, profile.flow)
    nodes = expanded.resolve_nodes()
    return {
        "valid": True,
        "name": profile.name,
        "buildOrder": build_order(expanded.dependencies),
        "instances": list(expanded.instances),
        "onFail": {
            node.id: node.gate.on_fail.model_dump()
            for node in nodes
            if node.gate and node.gate.on_fail
        },
    }


def load_config(home: Path) -> WorkflowConfig:
    try:
        return ResourceBundle(home).model("config.yaml", WorkflowConfig)
    except WorkflowError as exc:
        if exc.code != "workflow_invalid":
            raise
        raise WorkflowError(
            "config_invalid",
            "config.yaml 结构不合法",
            "config.yaml 只接受 artifacts_dir、workflow（required_fragments、assurance_rules、"
            "excluded_paths）与 registry（url、version、path）；registry.url 只接受 https、ssh、"
            "user@host:path 与 file:/// 形式且不能内嵌凭据；"
            "workflow.generated_dirs 已删除，把其中的名称原样移到 workflow.excluded_paths；"
            "删除 schema、schemas、schema_selection、context、rules、default_profile 等旧字段。",
        ) from exc


def project_constraints(home: Path) -> ProjectWorkflow:
    project = ProjectWorkflow.model_validate(load_config(home).workflow or {})
    if project.assurance_rules:
        relative_path(project.assurance_rules)
    return project


def check_constraints(project: ProjectWorkflow, expanded: FragmentExpander) -> None:
    selected = {instance.use for instance in expanded.instances.values()}
    if not set(project.required_fragments) <= selected:
        raise WorkflowError(
            "project_constraint",
            "Plan 缺少项目要求的 Fragment",
            "按 config.yaml 的 workflow.required_fragments 补齐实例后重新提交。",
        )
    if project.assurance_rules and not any(
        node.gate and node.gate.assurance for node in expanded.leaves.values()
    ):
        raise WorkflowError(
            "project_constraint",
            "项目保障规则要求 Plan 含最终保障节点",
            "在 flow 末尾加入 change-assurance 实例，并让它依赖全部交付分支。",
        )


def assurance_rules(
    bundle: ResourceBundle, nodes: list[ResolvedNode], project: ProjectWorkflow
) -> AssuranceRules | None:
    """Merge the Plan's and the project's assurance rules, read live from disk."""
    paths = {node.gate.assurance for node in nodes if node.gate and node.gate.assurance}
    if project.assurance_rules:
        paths.add(project.assurance_rules)
    by_id: dict[str, AssuranceRule] = {}
    unknown: Literal["fail", "warn"] = "warn"
    for path in sorted(paths):
        loaded = bundle.model(path, AssuranceRules)
        # Any file that fails unknown paths wins, so a Fragment cannot relax the project.
        if loaded.unknown_paths == "fail":
            unknown = "fail"
        for rule in loaded.rules:
            for pattern in rule.paths:
                relative_path(pattern, glob=True)
            if any(not re.fullmatch(KEBAB_RE, capability) for capability in rule.requires):
                raise WorkflowError("workflow_invalid", "审查能力名称不合法")
            if rule.id in by_id and by_id[rule.id] != rule:
                raise WorkflowError("rule_conflict", "项目与模板保障规则同名但内容冲突")
            by_id[rule.id] = rule
    return AssuranceRules(unknown_paths=unknown, rules=list(by_id.values())) if by_id else None


def check_assurance(nodes: list[ResolvedNode], rules: AssuranceRules | None) -> None:
    final = [node.id for node in nodes if node.gate and node.gate.assurance]
    if rules is None:
        return
    if len(final) != 1:
        raise WorkflowError("invalid_assurance", "代码保障必须有唯一最终 Assurance")
    graph = {node.id: set(node.requires) for node in nodes}
    previous = ancestors(graph, final[0])
    for node in nodes:
        if node.gate and node.gate.evidence and node.id not in previous:
            raise WorkflowError("invalid_assurance", "所有代码审查必须先于最终 Assurance")
        if node.id not in (final[0], *previous) and final[0] not in ancestors(graph, node.id):
            raise WorkflowError("invalid_assurance", "最终 Assurance 必须覆盖所有交付分支")


def spec_digest(spec: PlanSpec) -> str:
    return digest(spec.model_dump(by_alias=True))


@dataclass
class CompiledSpec:
    spec: PlanSpec

    @property
    def digest(self) -> str:
        return spec_digest(self.spec)

    def result(self) -> dict:
        return {
            "valid": True,
            "digest": self.digest,
            "spec": self.spec.model_dump(by_alias=True, exclude_none=True),
        }


def load_request(home: Path, path: str) -> PlanRequest:
    return ResourceBundle(home).model(relative_path(path), PlanRequest)


def compile_request(home: Path, request: PlanRequest) -> CompiledSpec:
    catalog = WorkflowCatalog(home)
    if request.based_on:
        catalog.profile(request.based_on)
    project = project_constraints(home)
    expanded = compile_flow(catalog, request.flow)
    check_constraints(project, expanded)
    nodes = expanded.resolve_nodes()
    check_assurance(nodes, assurance_rules(catalog.bundle, nodes, project))
    return CompiledSpec(PlanSpec(based_on=request.based_on, flow=request.flow, nodes=nodes))
