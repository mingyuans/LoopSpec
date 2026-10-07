"""Strict data models for Fragments, Profiles, Plans and Change-level state."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

from .models import KEBAB_RE, GateOutputs, GateTemplates

CHANGE_RE = r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$"
PLAN_RE = r"^[0-9]{3}$"
DIGEST_RE = r"^[0-9a-f]{64}$"


class StrictModel(BaseModel):
    model_config = {"extra": "forbid", "strict": True, "populate_by_name": True}


class FailurePolicy(StrictModel):
    reset: list[str] = Field(min_length=1, max_length=256)
    max_retries: int = Field(default=3, ge=0, le=100)


class CodeEvidence(StrictModel):
    provides: list[str] = Field(min_length=1, max_length=64)
    paths: list[str] = Field(min_length=1, max_length=128)


class WorkflowGate(StrictModel):
    outputs: GateOutputs
    templates: GateTemplates | None = None
    evidence: CodeEvidence | None = None
    assurance: str | None = None

    @model_validator(mode="after")
    def separate_system_gate(self) -> WorkflowGate:
        if self.assurance is not None and self.evidence is not None:
            raise ValueError("assurance 与普通代码证据不能同时定义")
        if self.outputs.pass_ == self.outputs.fail:
            raise ValueError("PASS 与 FAIL 输出不能相同")
        return self


class ResolvedGate(WorkflowGate):
    # Compiled form: at most one on_fail per Gate, reset already expanded to leaves.
    on_fail: FailurePolicy | None = None


class Node(StrictModel):
    id: str = Field(pattern=KEBAB_RE)
    description: str = ""
    use: str | None = Field(default=None, pattern=KEBAB_RE)
    requires: list[str] = Field(default_factory=list, max_length=256)
    generates: str | None = None
    instruction: str | None = None
    template: str | None = None
    tracks: str | None = None
    gate: WorkflowGate | None = None
    on_fail: FailurePolicy | None = None

    @model_validator(mode="after")
    def check_form(self) -> Node:
        execution = (self.generates, self.instruction, self.template, self.tracks, self.gate)
        if self.use is not None:
            if any(item is not None for item in execution):
                raise ValueError("use 引用与执行定义互斥")
        else:
            if (self.generates is None) == (self.gate is None):
                raise ValueError("执行 Node 必须且只能定义 generates 或 gate")
            if self.on_fail is not None and self.gate is None:
                raise ValueError("普通产物 Node 不定义业务失败策略")
        if len(set(self.requires)) != len(self.requires):
            raise ValueError("requires 不能重复")
        return self


class Fragment(StrictModel):
    version: Literal[1] = 1
    name: str = Field(pattern=KEBAB_RE)
    description: str = ""
    nodes: list[Node] = Field(min_length=1, max_length=256)

    @model_validator(mode="after")
    def unique_nodes(self) -> Fragment:
        if len({node.id for node in self.nodes}) != len(self.nodes):
            raise ValueError("同一 Fragment 的 Node ID 必须唯一")
        return self


class FragmentRef(StrictModel):
    id: str = Field(pattern=KEBAB_RE)
    use: str = Field(pattern=KEBAB_RE)
    requires: list[str] = Field(default_factory=list, max_length=256)
    # Same syntax as a reference node: reset names upstream instances of the same flow.
    on_fail: FailurePolicy | None = None


class Profile(StrictModel):
    version: Literal[1] = 1
    name: str = Field(pattern=KEBAB_RE)
    description: str = ""
    flow: list[FragmentRef] = Field(min_length=1, max_length=256)
    guidance: list[str] = Field(default_factory=list, max_length=128)


class PlanRequest(StrictModel):
    """What an Agent writes: the whole task's flow, optionally based on a Profile."""

    based_on: str | None = Field(default=None, pattern=KEBAB_RE)
    flow: list[FragmentRef] = Field(min_length=1, max_length=256)
    # Required only for a revision of an approved Plan; must equal its meta.revision.
    base_revision: int | None = Field(default=None, ge=1)


class ProjectWorkflow(StrictModel):
    required_fragments: list[str] = Field(default_factory=list, max_length=64)
    assurance_rules: str | None = None
    # Only tool-generated directories the engine recognises, never arbitrary business excludes.
    generated_dirs: list[str] = Field(default_factory=list, max_length=64)


class AssuranceRule(StrictModel):
    id: str = Field(pattern=KEBAB_RE)
    paths: list[str] = Field(min_length=1, max_length=128)
    requires: list[str] = Field(min_length=1, max_length=64)
    repair_fragment: str = Field(pattern=KEBAB_RE)


class AssuranceRules(StrictModel):
    version: Literal[1] = 1
    unknown_paths: Literal["fail"] = "fail"
    rules: list[AssuranceRule] = Field(min_length=1, max_length=256)


class ResolvedNode(StrictModel):
    id: str
    fragment: str
    description: str | None = None
    requires: list[str] = Field(default_factory=list)
    generates: str | None = None
    instruction: str | None = None
    template: str | None = None
    tracks: str | None = None
    gate: ResolvedGate | None = None


class PlanSpec(StrictModel):
    """The execution graph a human confirms; `nodes` is what the CLI navigates."""

    based_on: str | None = Field(default=None, pattern=KEBAB_RE)
    flow: list[FragmentRef] = Field(min_length=1, max_length=256)
    nodes: list[ResolvedNode] = Field(min_length=1, max_length=1024)

    @model_validator(mode="after")
    def closed_graph(self) -> PlanSpec:
        identities = [node.id for node in self.nodes]
        if len(set(identities)) != len(identities):
            raise ValueError("节点 ID 必须唯一")
        known = set(identities)
        for node in self.nodes:
            if not set(node.requires) <= known:
                raise ValueError("requires 引用不存在的节点")
            if node.gate and node.gate.on_fail and not set(node.gate.on_fail.reset) <= known:
                raise ValueError("on_fail.reset 引用不存在的节点")
        return self


class PlanMeta(StrictModel):
    plan: str = Field(pattern=PLAN_RE)
    status: Literal["draft", "approved", "archived"]
    revision: int = Field(ge=0, le=100000)
    digest: str = Field(pattern=DIGEST_RE)
    approved_at: str | None = None
    note: str | None = Field(default=None, max_length=16384)
    created: str
    archived_at: str | None = None
    archive_note: str | None = Field(default=None, max_length=16384)

    @model_validator(mode="after")
    def consistent(self) -> PlanMeta:
        if (self.revision == 0) != (self.approved_at is None):
            raise ValueError("revision 与 approved_at 必须同时表示是否确认过")
        if self.status == "draft" and self.revision != 0:
            raise ValueError("draft Plan 不能有已确认修订")
        if self.status == "approved" and self.revision < 1:
            raise ValueError("approved Plan 必须有已确认修订")
        if (self.status == "archived") != (self.archived_at is not None):
            raise ValueError("只有 archived Plan 带归档时间")
        if self.archive_note is not None and self.status != "archived":
            raise ValueError("只有 archived Plan 带归档说明")
        return self


class PlanDocument(StrictModel):
    meta: PlanMeta
    spec: PlanSpec


class ChangeState(StrictModel):
    """`changes/<name>/.workflow.yaml`: only what belongs to the Change itself.

    Plan pointers are not stored; the open and active Plan are derived from each
    `plan.yaml`, so no write can leave a pointer and a Plan disagreeing.
    """

    format_version: Literal[4] = 4
    change_name: str = Field(pattern=CHANGE_RE)
    created: str
    baseline: str | None = Field(default=None, pattern=r"^([0-9a-f]{40}|[0-9a-f]{64})$")
    repository: str | None = None

    @model_validator(mode="after")
    def pinned_together(self) -> ChangeState:
        if (self.baseline is None) != (self.repository is None):
            raise ValueError("baseline 与 repository 必须同时固定")
        return self


class FailureReport(StrictModel):
    verdict: Literal["FAIL"]
    summary: str = Field(min_length=1, max_length=16384)

    @model_validator(mode="after")
    def meaningful_summary(self) -> FailureReport:
        if not self.summary.strip():
            raise ValueError("失败摘要不能为空白")
        return self
