"""Review rounds and input evidence for code Gates; a round id is not a credential."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Literal

from pydantic import Field

from .errors import WorkflowError
from .workflow_diff import DiffSnapshot, collect_diff
from .workflow_io import (
    ResourceBundle,
    archive_file,
    atomic_write,
    byte_hash,
    directory,
    exists,
    read_bytes,
    relative_path,
    write_lock,
    write_yaml,
)
from .workflow_models import ResolvedNode, StrictModel
from .workflow_state import LoadedPlan, open_change
from .workflow_yaml import parse_yaml


class GateReport(StrictModel):
    verdict: Literal["PASS", "FAIL"]
    summary: str = Field(min_length=1, max_length=16384)


class Begin(StrictModel):
    gate: str
    plan_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    baseline: str
    round: int = Field(ge=1, le=2048)
    round_id: str
    paths: list[str]
    provides: list[str]
    scope_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    consumed: bool = False


class Evidence(StrictModel):
    gate: str
    plan_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    baseline: str
    round: int = Field(ge=1)
    verdict: Literal["PASS", "FAIL"]
    paths: list[str]
    provides: list[str]
    scope_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    report_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    system: bool = False


def evidence_path(identity: str) -> str:
    return f".gates/{relative_path(identity)}/evidence.yaml"


def begin_path(identity: str) -> str:
    return f".gates/{relative_path(identity)}/begin.yaml"


def rounds_dir(identity: str) -> str:
    return f".gate-rounds/{relative_path(identity)}"


def valid_evidence(
    loaded: LoadedPlan,
    node: ResolvedNode,
    verdict: str = "PASS",
    snapshot: DiffSnapshot | None = None,
) -> tuple[bool, str | None]:
    assert node.gate
    path = evidence_path(node.id)
    if not exists(loaded.root, path):
        return False, "evidence_missing"
    evidence = ResourceBundle(loaded.root).model(path, Evidence)
    policy = node.gate.evidence
    paths = policy.paths if policy else ["**"]
    provides = policy.provides if policy else []
    if (
        evidence.gate != node.id
        or evidence.plan_digest != loaded.digest
        or evidence.baseline != loaded.change.state.baseline
        or evidence.paths != paths
        or evidence.provides != provides
        or evidence.verdict != verdict
        or evidence.system != bool(node.gate.assurance)
    ):
        return False, "evidence_stale"
    report_path = node.gate.outputs.pass_ if verdict == "PASS" else node.gate.outputs.fail
    if not node.gate.assurance:
        if not exists(loaded.root, begin_path(node.id)):
            return False, "evidence_stale"
        context = ResourceBundle(loaded.root).model(begin_path(node.id), Begin)
        if (
            not context.consumed
            or context.round != evidence.round
            or context.plan_digest != evidence.plan_digest
            or context.scope_digest != evidence.scope_digest
        ):
            return False, "evidence_stale"
    if (
        not exists(loaded.root, report_path)
        or byte_hash(read_bytes(loaded.root, report_path)) != evidence.report_hash
    ):
        return False, "evidence_stale"
    snapshot = snapshot or collect_diff(loaded)
    if node.gate.assurance and snapshot.diverged:
        # A commit made after assurance can ship unreviewed content behind a reviewed worktree.
        return False, "evidence_stale"
    expected = snapshot.diff_digest if node.gate.assurance else snapshot.scope_digest(paths)
    return (True, None) if evidence.scope_digest == expected else (False, "evidence_stale")


def code_gate(loaded: LoadedPlan, identity: str) -> ResolvedNode:
    node = next((item for item in loaded.spec.nodes if item.id == identity), None)
    if not node or not node.gate or not node.gate.evidence:
        raise WorkflowError("not_code_gate", "此节点不是可记录代码审查证据的 Gate")
    return node


def next_round(root: Path, identity: str) -> int:
    with directory(root, rounds_dir(identity), create=True) as fd:
        names = os.listdir(fd)
    if len(names) > 2048:
        raise WorkflowError("resource_limit", "Gate 审查轮次超过限制")
    return (
        max((int(name[:-5]) for name in names if re.fullmatch(r"[0-9]{3,}\.yaml", name)), default=0)
        + 1
    )


def node_entry(loaded: LoadedPlan, identity: str) -> dict:
    from .workflow_runtime import status

    return next(item for item in status(loaded)["nodes"] if item["id"] == identity)


def begin(home: Path, name: str, identity: str) -> dict:
    from .workflow_attempts import settled

    ctx = open_change(home, name)
    with write_lock(ctx.root):
        loaded = settled(open_change(home, name))
        root = loaded.root
        node = code_gate(loaded, identity)
        entry = node_entry(loaded, identity)
        if entry["status"] != "ready":
            raise WorkflowError("node_not_ready", "只有就绪代码 Gate 才能开始新审查轮次")
        snapshot = collect_diff(loaded)
        assert node.gate and node.gate.evidence
        policy = node.gate.evidence
        round_number = next_round(root, identity)
        round_id = f"{loaded.plan_id}.{loaded.document.meta.revision}:{identity}:{round_number}"
        context = Begin(
            gate=identity,
            plan_digest=loaded.digest,
            baseline=snapshot.baseline,
            round=round_number,
            round_id=round_id,
            paths=policy.paths,
            provides=policy.provides,
            scope_digest=snapshot.scope_digest(policy.paths),
        )
        write_yaml(
            root,
            f"{rounds_dir(identity)}/{round_number:03d}.yaml",
            context.model_dump(),
            exclusive=True,
        )
        write_yaml(root, begin_path(identity), context.model_dump())
        return {
            "gate": identity,
            "roundId": round_id,
            "scopeDigest": context.scope_digest,
            "baseline": context.baseline,
            "planDigest": context.plan_digest,
            "paths": [
                {
                    "path": item["path"],
                    "kind": item["kind"],
                    "index": item["index"],
                    "worktree": item["worktree"],
                }
                for item in snapshot.scope(policy.paths)
            ],
            "warnings": snapshot.warnings(),
            "instruction": (
                "本轮编号不是认证凭据。审查此固定输入后，使用 gate record 提交报告；"
                "代码变化需重新 begin。warnings 不为空时，在报告摘要中记录这些告警。"
            ),
        }


def record(
    home: Path, name: str, identity: str, round_id: str | None, report_path: str | None
) -> dict:
    from .workflow_attempts import settled

    ctx = open_change(home, name)
    with write_lock(ctx.root):
        loaded = settled(open_change(home, name))
        node = next((item for item in loaded.spec.nodes if item.id == identity), None)
        if node and node.gate and node.gate.assurance:
            if round_id is not None or report_path is not None:
                raise WorkflowError(
                    "option_conflict",
                    "保障节点由系统检查，不接受 --round 或 --report",
                    f"直接执行 loopspec gate record -c {name} -n {identity}。",
                )
            from .workflow_assurance import check

            return check(loaded, node)
        node = code_gate(loaded, identity)
        if round_id is None or report_path is None:
            raise WorkflowError(
                "option_required",
                "代码 Gate 需要 --round 与 --report",
                f"先 loopspec gate begin -c {name} -n {identity}，审查后再提交报告。",
            )
        root = loaded.root
        entry = node_entry(loaded, identity)
        if entry["status"] != "ready":
            raise WorkflowError("node_not_ready", "节点尚未就绪或已经消费本轮结论")
        if not exists(root, begin_path(identity)):
            raise WorkflowError("round_stale", "尚未开始审查轮次，请先 gate begin")
        context = ResourceBundle(root).model(begin_path(identity), Begin)
        assert node.gate and node.gate.evidence
        if (
            context.consumed
            or context.round_id != round_id
            or context.gate != identity
            or context.plan_digest != loaded.digest
            or context.baseline != loaded.change.state.baseline
            or context.paths != node.gate.evidence.paths
            or context.provides != node.gate.evidence.provides
            or context.round != next_round(root, identity) - 1
        ):
            raise WorkflowError("round_stale", "本轮编号已消费、过期或属于其他输入")
        path = relative_path(report_path)
        if not path.startswith("artifacts/"):
            raise WorkflowError("unsafe_report", "报告必须位于活动 Plan 的 artifacts 目录内")
        data = read_bytes(root, path)
        parsed = data
        if data.startswith(b"---\n"):
            pieces = data.split(b"\n---", 1)
            if len(pieces) != 2:
                raise WorkflowError("invalid_verdict", "报告头部未闭合")
            parsed = pieces[0][4:]
        try:
            report = GateReport.model_validate(parse_yaml(parsed))
        except (ValueError, UnicodeError) as exc:
            raise WorkflowError(
                "invalid_verdict", "报告必须包含明确结论与摘要，不能自报证据范围"
            ) from exc
        if not report.summary.strip():
            raise WorkflowError("invalid_verdict", "报告摘要不能为空白")
        snapshot = collect_diff(loaded)
        if snapshot.scope_digest(context.paths) != context.scope_digest:
            raise WorkflowError("review_input_changed", "审查期间输入变化，请重新 begin")
        # 先消费编号；任何后续 IO 错误只能开始新轮次，不能重复提交旧编号。
        context.consumed = True
        write_yaml(root, begin_path(identity), context.model_dump())
        for output in (node.gate.outputs.pass_, node.gate.outputs.fail):
            if exists(root, output):
                destination = f"{rounds_dir(identity)}/prior/{context.round:03d}/" + output
                archive_file(root, output, destination)
        output = node.gate.outputs.pass_ if report.verdict == "PASS" else node.gate.outputs.fail
        atomic_write(root, output, data)
        snapshot = collect_diff(loaded)
        if snapshot.scope_digest(context.paths) != context.scope_digest:
            raise WorkflowError("review_input_changed", "记录期间代码输入变化，未产生有效证据")
        evidence = Evidence(
            gate=identity,
            plan_digest=context.plan_digest,
            baseline=context.baseline,
            round=context.round,
            verdict=report.verdict,
            paths=context.paths,
            provides=context.provides,
            scope_digest=context.scope_digest,
            report_hash=byte_hash(data),
        )
        write_yaml(root, evidence_path(identity), evidence.model_dump())
        return {
            "gate": identity,
            "verdict": report.verdict,
            "roundId": context.round_id,
            "evidenceRecorded": True,
            "warnings": snapshot.warnings(),
        }
