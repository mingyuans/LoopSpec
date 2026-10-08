"""Plan lifecycle: draft, approval, in-place revision, archive and rollback.

Every command has exactly one write that decides the outcome (design D8): an interrupted
command leaves the Change either as it was or as the command made it, never in between.
"""

from __future__ import annotations

from pathlib import Path

from .errors import WorkflowError
from .workflow_attempts import (
    build_record,
    committed_records,
    downstream,
    files_for,
    finish,
    settle,
    write_record,
)
from .workflow_git import fixed_baseline
from .workflow_io import atomic_write, byte_hash, exists, read_bytes, write_lock
from .workflow_journal import event_line, plan_state_template, record, with_warnings
from .workflow_models import PlanDocument, PlanMeta, PlanRequest, PlanSpec
from .workflow_planning import CompiledSpec, compile_request, load_request
from .workflow_state import (
    ChangeContext,
    LoadedPlan,
    active_plan,
    check_plan_id,
    not_active,
    now,
    open_change,
    plan_path,
    read_plan,
    write_plan,
    write_state,
)


def needs_baseline(spec: PlanSpec) -> bool:
    return any(node.gate and (node.gate.evidence or node.gate.assurance) for node in spec.nodes)


def baseline_view(ctx: ChangeContext) -> dict:
    return {"baseline": ctx.state.baseline, "repository": ctx.state.repository}


def check_repository(ctx: ChangeContext, spec: PlanSpec) -> None:
    state = ctx.state
    if state.baseline is None:
        if needs_baseline(spec):
            raise WorkflowError(
                "baseline_required",
                "代码 Gate 与保障需要 Git 仓库与固定基线",
                "在 Git 仓库中使用。",
            )
        return
    _, repository = fixed_baseline(ctx.root, state.baseline)
    if repository != state.repository:
        raise WorkflowError("repository_changed", "Git 仓库身份与 Change 固定的不一致")


def frozen_check(loaded: LoadedPlan, spec: PlanSpec) -> tuple[list[str], list[str]]:
    """Revision rules (design D5): returns (nodes to re-run, added instances)."""
    from .workflow_runtime import status

    report = status(loaded)
    old_nodes = {node.id: node for node in loaded.spec.nodes}
    new_nodes = {node.id: node for node in spec.nodes}
    states = {entry["id"]: entry["status"] for entry in report["nodes"]}
    failed = {key for key, value in states.items() if value in ("failed", "exhausted")}
    current = next((key for key, value in states.items() if value == "ready"), None)
    frozen = {key for key, value in states.items() if value == "done"} | failed
    if current:
        frozen.add(current)
    for item in committed_records(loaded):
        frozen.update(set(item.reset) & set(old_nodes))
    invalidated: set[str] = set()
    for identity in sorted(frozen):
        original, candidate = old_nodes[identity], new_nodes.get(identity)
        if candidate is None:
            raise WorkflowError(
                "node_frozen",
                f"冻结节点 {identity} 不能删除或改名",
                "保留已完成、当前、失败或有返工记录的节点；"
                "任务已变化时先 plan archive 再重新规划。",
            )
        if candidate.model_copy(update={"requires": original.requires}) != original or not set(
            original.requires
        ) <= set(candidate.requires):
            raise WorkflowError(
                "node_frozen",
                f"冻结节点 {identity} 只能增加 requires，不能改写执行定义",
                "任务已变化时先 plan archive 再重新规划。",
            )
        if set(candidate.requires) != set(original.requires):
            invalidated.add(identity)
    rerun = downstream(spec.nodes, invalidated) & set(old_nodes)
    if not failed <= rerun:
        raise WorkflowError(
            "failure_pending",
            "修订必须让有效 FAIL 的 Gate 重新执行",
            "先 plan rollback 处理失败，或让失败 Gate 依赖新增节点后再修订。",
        )
    added = [ref.id for ref in spec.flow if ref.id not in {old.id for old in loaded.spec.flow}]
    return sorted(rerun), added


def validate(home: Path, name: str, path: str) -> dict:
    """Read-only: compile and check a request; with an approved Plan it previews a revision."""
    ctx = open_change(home, name)
    request = load_request(home, path)
    if ctx.active_plan() is None:
        if request.base_revision is not None:
            raise WorkflowError(
                "stale_revision",
                "没有已确认的 Plan，请求不能带 base_revision",
                "删除 base_revision。",
            )
        compiled = compile_request(home, request)
        return {
            **compiled.result(),
            "mode": "plan",
            "changeName": name,
            **baseline_view(ctx),
            "nextSteps": [f"loopspec plan create -c {name} -f {path}"],
        }
    loaded = active_plan(ctx)
    meta = loaded.document.meta
    if request.base_revision != meta.revision:
        raise WorkflowError(
            "stale_revision",
            "修订请求的 base_revision 必须等于当前修订",
            f"当前修订为 {meta.revision}。",
        )
    compiled = compile_request(home, request)
    rerun, added = frozen_check(loaded, compiled.spec)
    return {
        **compiled.result(),
        "mode": "revision",
        "changeName": name,
        "plan": loaded.plan_id,
        "baseRevision": meta.revision,
        "revision": meta.revision + 1,
        "addedInstances": added,
        "rerunNodes": rerun,
        **baseline_view(ctx),
        "message": "展示新摘要、新增实例与将重新执行的节点；人确认后才 plan approve -f。",
        "nextSteps": [
            f"loopspec plan approve -c {name} -p {loaded.plan_id} -f {path} "
            f"--digest {compiled.digest}"
        ],
    }


def create(home: Path, name: str, path: str, note: str | None = None) -> dict:
    """Commit point: writing the draft's plan.yaml (design D8)."""
    ctx = open_change(home, name)
    with write_lock(ctx.root):
        ctx = open_change(home, name)
        request = load_request(home, path)
        if request.base_revision is not None:
            raise WorkflowError(
                "option_conflict",
                "带 base_revision 的是修订请求",
                "修订用 plan validate -f 预览、plan approve -f 确认。",
            )
        active = ctx.active_plan()
        if active is not None:
            raise WorkflowError(
                "plan_active",
                "已有确认的活动 Plan，不能新建 Plan",
                f"原计划需调整时用 plan validate -c {name} -f <修订请求> 预览、"
                "plan approve -f 确认；"
                f"任务已变化时先取得人同意，再 plan archive -c {name} -p {active}。",
            )
        compiled = compile_request(home, request)
        draft = ctx.open_plan()
        if draft is not None:
            document = ctx.documents()[draft]
            document.meta.digest = compiled.digest
            if note is not None:
                document.meta.note = note
            document.spec = compiled.spec
            write_plan(ctx.root, document)
            line = event_line(now(), "replace-draft", f"digest {compiled.digest[:8]}", note=note)
            failed = record(ctx.root, plan_path(draft, "state.md"), line)
            return with_warnings(created(ctx, document, compiled, replaced=True), [failed])
        plan_id = ctx.next_plan()
        state = ctx.state
        if state.baseline is None:
            # Fixed before the draft exists; an interrupted create re-uses this baseline.
            try:
                state.baseline, state.repository = fixed_baseline(ctx.root)
            except WorkflowError:
                if needs_baseline(compiled.spec):
                    raise
            else:
                write_state(ctx.root, state)
        if not exists(ctx.root, plan_path(plan_id, "state.md")):
            atomic_write(
                ctx.root,
                plan_path(plan_id, "state.md"),
                plan_state_template(plan_id).encode(),
                exclusive=True,
            )
        document = PlanDocument(
            meta=PlanMeta(
                plan=plan_id,
                status="draft",
                revision=0,
                digest=compiled.digest,
                note=note,
                created=now(),
            ),
            spec=compiled.spec,
        )
        write_plan(ctx.root, document)
        line = event_line(
            document.meta.created, "create", f"digest {compiled.digest[:8]}", note=note
        )
        failed = record(ctx.root, plan_path(plan_id, "state.md"), line)
        return with_warnings(created(ctx, document, compiled, replaced=False), [failed])


def created(
    ctx: ChangeContext, document: PlanDocument, compiled: CompiledSpec, replaced: bool
) -> dict:
    plan_id = document.meta.plan
    return {
        **compiled.result(),
        "changeName": ctx.name,
        "plan": plan_id,
        "status": "draft",
        "replacedDraft": replaced,
        **baseline_view(ctx),
        "message": "草稿不会执行；展示 plan show 的内容并取得人的明确确认后才能 plan approve。",
        "nextSteps": [f"loopspec plan show -c {ctx.name} -p {plan_id}"],
    }


def show(home: Path, name: str, plan_id: str | None = None) -> dict:
    ctx = open_change(home, name)
    selected = check_plan_id(plan_id) if plan_id else ctx.open_plan()
    if selected is None:
        raise WorkflowError(
            "plan_not_found", "没有未结束的 Plan", f"用 plan list -c {name} 查看历史 Plan。"
        )
    document = read_plan(ctx.root, selected)
    return {
        "changeName": name,
        "plan": selected,
        "active": ctx.active_plan() == selected,
        "meta": document.meta.model_dump(),
        "spec": document.spec.model_dump(by_alias=True, exclude_none=True),
        **baseline_view(ctx),
    }


def plan_list(home: Path, name: str) -> dict:
    ctx = open_change(home, name)
    items = []
    for plan_id, document in ctx.documents().items():
        meta = document.meta
        items.append(
            {
                "plan": plan_id,
                "status": meta.status,
                "revision": meta.revision,
                "active": meta.status == "approved",
                "note": meta.note,
                "created": meta.created,
                "approvedAt": meta.approved_at,
                "archivedAt": meta.archived_at,
                "archiveNote": meta.archive_note,
            }
        )
    return {"changeName": name, "plans": items, **baseline_view(ctx)}


def approved(
    ctx: ChangeContext, document: PlanDocument, *, already: bool, rerun: list[str]
) -> dict:
    return {
        "changeName": ctx.name,
        "plan": document.meta.plan,
        "status": "approved",
        "revision": document.meta.revision,
        "digest": document.meta.digest,
        "alreadyApproved": already,
        "rerunNodes": rerun,
        "nextSteps": [f"loopspec change status {ctx.name}"],
    }


def approve(home: Path, name: str, plan_id: str, expected: str, path: str | None = None) -> dict:
    check_plan_id(plan_id)
    ctx = open_change(home, name)
    with write_lock(ctx.root):
        ctx = open_change(home, name)
        if path is not None:
            return approve_revision(ctx, plan_id, path, expected)
        document = read_plan(ctx.root, plan_id)
        meta = document.meta
        if meta.status == "archived":
            raise WorkflowError("plan_archived", "已归档的 Plan 不能确认", "重新 plan create。")
        if meta.status == "approved":
            if expected != meta.digest:
                raise WorkflowError("plan_changed", "摘要与已确认的 Plan 不一致")
            return approved(ctx, document, already=True, rerun=[])
        # Recompile against current Fragments and config: what is approved is what was shown.
        compiled = compile_request(
            home, PlanRequest(based_on=document.spec.based_on, flow=document.spec.flow)
        )
        if expected != meta.digest or compiled.digest != meta.digest:
            raise WorkflowError(
                "plan_changed",
                "确认的摘要与当前草稿或其重新编译结果不一致",
                f"重新 plan show -c {name} -p {plan_id} 展示并取得确认；"
                "Fragment 变化时重新 plan create。",
            )
        check_repository(ctx, document.spec)
        meta.status = "approved"
        meta.revision = 1
        meta.approved_at = now()
        write_plan(ctx.root, document)
        line = event_line(meta.approved_at, "approve", "revision 1", f"digest {meta.digest[:8]}")
        failed = record(ctx.root, plan_path(plan_id, "state.md"), line)
        return with_warnings(approved(ctx, document, already=False, rerun=[]), [failed])


def approve_revision(ctx: ChangeContext, plan_id: str, path: str, expected: str) -> dict:
    """record.yaml, then plan.yaml (commit point), then archive the re-run nodes' files."""
    loaded = active_plan(ctx, plan_id)
    settle(loaded)
    meta = loaded.document.meta
    request = load_request(ctx.home, path)
    compiled = compile_request(ctx.home, request)
    if compiled.digest == meta.digest:
        if expected != meta.digest:
            raise WorkflowError("plan_changed", "摘要与已确认的 Plan 不一致")
        return approved(ctx, loaded.document, already=True, rerun=[])
    if request.base_revision != meta.revision:
        raise WorkflowError(
            "stale_revision",
            "修订请求的 base_revision 必须等于当前修订",
            f"当前修订为 {meta.revision}；重新 plan validate 预览并取得确认。",
        )
    if expected != compiled.digest:
        raise WorkflowError(
            "plan_changed",
            "确认的摘要与重新编译的修订不一致",
            f"重新 plan validate -c {ctx.name} -f {path} 展示并取得确认。",
        )
    check_repository(ctx, compiled.spec)
    rerun, _ = frozen_check(loaded, compiled.spec)
    revision = meta.revision + 1
    document = loaded.document.model_copy(deep=True)
    document.spec = compiled.spec
    document.meta.digest = compiled.digest
    document.meta.revision = revision
    document.meta.approved_at = now()
    # Files are listed against the new spec, which is what the record is checked against later.
    revised = LoadedPlan(ctx, plan_id, document)
    reset = [identity for identity in rerun if any(n.id == identity for n in compiled.spec.nodes)]
    attempt = None
    if reset:
        attempt = build_record(
            loaded,
            "revision",
            reset,
            files_for(revised, reset),
            target_digest=compiled.digest,
            revision=revision,
        )
        write_record(revised, attempt)
    write_plan(ctx.root, document)
    if attempt is not None:
        finish(revised, attempt)
    line = event_line(
        document.meta.approved_at,
        "revise",
        f"revision {meta.revision} → {revision}",
        f"digest {compiled.digest[:8]}",
        f"rerun: {', '.join(rerun) or '-'}",
    )
    failed = record(ctx.root, plan_path(plan_id, "state.md"), line)
    return with_warnings(approved(ctx, document, already=False, rerun=rerun), [failed])


def archive(home: Path, name: str, plan_id: str, note: str | None = None) -> dict:
    """Commit point: the single write of plan.yaml as archived."""
    check_plan_id(plan_id)
    ctx = open_change(home, name)
    with write_lock(ctx.root):
        ctx = open_change(home, name)
        document = read_plan(ctx.root, plan_id)
        meta = document.meta
        failed: list[str | None] = []
        if meta.status != "archived":
            if meta.status == "approved":
                settle(LoadedPlan(ctx, plan_id, document))
            meta.status = "archived"
            meta.archived_at = now()
            meta.archive_note = note
            write_plan(ctx.root, document)
            stamp = meta.archived_at
            failed = [
                record(
                    ctx.root,
                    plan_path(plan_id, "state.md"),
                    event_line(stamp, "archive", note=note),
                ),
                record(
                    ctx.root, "state.md", event_line(stamp, f"archive plan {plan_id}", note=note)
                ),
            ]
        return with_warnings(
            {
                "changeName": name,
                "plan": plan_id,
                "status": "archived",
                "archivedAt": meta.archived_at,
                "message": "Plan 目录原样保留；需要时重新为完整任务制定新 Plan 并取得确认。",
                "nextSteps": [f"loopspec plan create -c {name} -f <请求文件>"],
            },
            failed,
        )


def rollback(home: Path, name: str, plan_id: str) -> dict:
    """Commit point: writing record.yaml; the listed files are archived afterwards."""
    check_plan_id(plan_id)
    ctx = open_change(home, name)
    with write_lock(ctx.root):
        ctx = open_change(home, name)
        if ctx.active_plan() is None:
            raise not_active(ctx)
        loaded = active_plan(ctx, plan_id)
        settle(loaded)
        from .workflow_runtime import status

        report = status(loaded)
        pending_rollback = report["pendingRollback"]
        if pending_rollback is None:
            if any(entry["status"] == "exhausted" for entry in report["nodes"]):
                raise WorkflowError(
                    "retries_exhausted",
                    "失败 Gate 没有 on_fail 或返工次数已用完",
                    "停下交给人决定：修订 Plan，或经人同意 plan archive 后重新规划。",
                )
            raise WorkflowError("no_failed_gate", "活动 Plan 中没有待返工的有效 FAIL")
        gate = next(node for node in loaded.spec.nodes if node.id == pending_rollback["gate"])
        assert gate.gate
        reset = pending_rollback["closure"]
        report_path = gate.gate.outputs.fail
        attempt = build_record(
            loaded,
            "rollback",
            reset,
            files_for(loaded, reset, last=report_path),
            gate=gate.id,
            failure_digest=byte_hash(read_bytes(loaded.root, report_path)),
        )
        write_record(loaded, attempt)
        finish(loaded, attempt)
        line = event_line(
            now(),
            "rollback",
            f"gate {gate.id}",
            f"attempt {attempt.seq}",
            f"reset: {', '.join(reset)}",
        )
        failed = record(ctx.root, plan_path(loaded.plan_id, "state.md"), line)
        return with_warnings(
            {
                "changeName": loaded.name,
                "plan": loaded.plan_id,
                "attempt": attempt.seq,
                "gate": gate.id,
                "reset": reset,
                "message": "已归档重置范围内的产物与报告；业务代码未回退。",
                "nextSteps": [f"loopspec change status {loaded.name}"],
            },
            [failed],
        )
