"""Change-level commands: create an unplanned Change and report its derived status."""

from __future__ import annotations

import os
import re
import stat
from pathlib import Path

from .errors import WorkflowError
from .workflow_io import atomic_write, directory, exists
from .workflow_journal import CHANGE_STATE_TEMPLATE, UNTRUSTED_STATE, state_view
from .workflow_models import PLAN_RE, ChangeState
from .workflow_state import (
    STATE_FILE,
    ChangeContext,
    LoadedPlan,
    changes_dir,
    check_change_name,
    check_plan_id,
    now,
    open_change,
    plan_ids,
    plan_path,
    read_plan,
    read_state,
    write_state,
)


def create(home: Path, name: str) -> dict:
    """mkdir → plans/ → state.md → .workflow.yaml (commit point); re-running finishes it."""
    check_change_name(name)
    parent = changes_dir(home)
    root = home / parent / name
    with directory(home, parent, create=True) as fd:
        try:
            os.mkdir(name, mode=0o700, dir_fd=fd)
        except FileExistsError:
            if not stat.S_ISDIR(os.stat(name, dir_fd=fd, follow_symlinks=False).st_mode):
                raise WorkflowError("unsafe_path", "需求路径不是目录") from None
        os.fsync(fd)
    if exists(root, STATE_FILE):
        state = read_state(root)
        return {
            "changeName": state.change_name,
            "changeRoot": str(root.absolute()),
            "reusedChange": True,
            "nextSteps": [f"loopspec change status {name}"],
        }
    with directory(root, "plans", create=True):
        pass
    if not exists(root, "state.md"):
        atomic_write(
            root,
            "state.md",
            CHANGE_STATE_TEMPLATE.encode(),
            exclusive=True,
        )
    write_state(root, ChangeState(change_name=name, created=now()), exclusive=True)
    return {
        "changeName": name,
        "changeRoot": str(root.absolute()),
        "reusedChange": False,
        "status": "unplanned",
        "isComplete": False,
        "nextSteps": planning_steps(name),
    }


def planning_steps(name: str) -> list[str]:
    return [
        "loopspec fragment list",
        "loopspec profile list",
        f"loopspec plan validate -c {name} -f <请求文件>",
        f"loopspec plan create -c {name} -f <请求文件>",
    ]


def plan_summaries(ctx: ChangeContext) -> list[dict]:
    return [
        {
            "plan": plan_id,
            "status": document.meta.status,
            "revision": document.meta.revision,
            "note": document.meta.note,
            "archivedAt": document.meta.archived_at,
        }
        for plan_id, document in ctx.documents().items()
    ]


def status(home: Path, name: str) -> dict:
    ctx = open_change(home, name)
    state = ctx.state
    open_plan, active = ctx.open_plan(), ctx.active_plan()
    result: dict = {
        "changeName": name,
        "baseline": state.baseline,
        "repository": state.repository,
        "activePlan": active,
        "openPlan": open_plan,
        "plans": plan_summaries(ctx),
        "state": state_view(ctx.root, "state.md"),
        "planState": None
        if open_plan is None
        else {"plan": open_plan, **state_view(ctx.root, plan_path(open_plan, "state.md"))},
        "untrustedData": UNTRUSTED_STATE,
        "isComplete": False,
    }
    if open_plan is None:
        return {
            **result,
            "status": "unplanned",
            "message": "尚无未结束 Plan：参考 Fragment/Profile 为完整任务编写请求并创建草稿。",
            "nextSteps": planning_steps(name),
        }
    if active is None:
        return {
            **result,
            "status": "planning",
            "message": "草稿 Plan 等待人确认；草稿不会执行。",
            "nextSteps": [f"loopspec plan show -c {name} -p {open_plan}"],
        }
    from .workflow_runtime import status as execution

    report = execution(LoadedPlan(ctx, active, ctx.documents()[active]))
    complete = report["isComplete"]
    return {
        **result,
        **report,
        "status": "complete" if complete else "active",
        "nextSteps": [f"loopspec change archive {name}"] if complete else report["nextSteps"],
    }


def next_step(home: Path, name: str) -> dict:
    report = status(home, name)
    node = None
    if report.get("nodes"):
        target = (report.get("pendingRollback") or {}).get("gate")
        node = next(
            (item for item in report["nodes"] if item["id"] == target),
            next(
                (item for item in report["nodes"] if item["status"] in ("ready", "exhausted")),
                None,
            ),
        )
    return {
        "changeName": name,
        "status": report["status"],
        "isComplete": report["isComplete"],
        "node": node,
        "nextSteps": report["nextSteps"],
    }


def history(home: Path, name: str, plan_id: str | None = None) -> dict:
    from .workflow_attempts import committed_records

    ctx = open_change(home, name)
    known = plan_ids(ctx.root)
    selected = check_plan_id(plan_id) if plan_id else ctx.open_plan()
    if selected is None and known:
        selected = known[-1]
    if selected is None:
        return {"changeName": name, "plan": None, "attempts": []}
    loaded = LoadedPlan(ctx, selected, read_plan(ctx.root, selected))
    return {
        "changeName": name,
        "plan": selected,
        "attempts": [
            {
                "seq": item.seq,
                "kind": item.kind,
                "created": item.created,
                "gate": item.gate,
                "reset": item.reset,
                "files": [move.model_dump() for move in item.files],
                "targetDigest": item.target_digest,
                "revision": item.revision,
            }
            for item in committed_records(loaded)
        ],
    }


def change_locations(home: Path, name: str) -> list[tuple[str, Path]]:
    check_change_name(name)
    found: list[tuple[str, Path]] = []
    parent = changes_dir(home)
    try:
        with directory(home, parent + "/" + name):
            found.append(("active", home / parent / name))
    except WorkflowError as exc:
        if not isinstance(exc.__cause__, FileNotFoundError):
            raise
    try:
        with directory(home, "archive") as fd:
            months = sorted(item for item in os.listdir(fd) if re.fullmatch(r"\d{4}-\d{2}", item))
    except WorkflowError as exc:
        if not isinstance(exc.__cause__, FileNotFoundError):
            raise
        months = []
    for month in months:
        try:
            with directory(home, f"archive/{month}/{name}"):
                found.append((f"archive/{month}", home / "archive" / month / name))
        except WorkflowError as exc:
            if not isinstance(exc.__cause__, FileNotFoundError):
                raise
    return found


def artifacts(home: Path, name: str) -> dict:
    """Every artifact the Change owns, grouped by Plan, including archived Plans and Changes."""
    from .workflow_runtime import output_files

    locations = []
    for label, root in change_locations(home, name):
        plans = []
        for plan_id in plan_ids(root):
            if not re.fullmatch(PLAN_RE, plan_id):
                continue
            meta = read_plan(root, plan_id).meta
            plan_root = root / "plans" / plan_id
            plans.append(
                {
                    "plan": plan_id,
                    "status": meta.status,
                    "artifacts": [
                        str(plan_root / path) for path in output_files(plan_root, "artifacts/*")
                    ],
                }
            )
        locations.append({"location": label, "changeRoot": str(root), "plans": plans})
    if not locations:
        raise WorkflowError("change_not_found", "需求不存在，也没有已归档的同名需求")
    return {"changeName": name, "locations": locations}
