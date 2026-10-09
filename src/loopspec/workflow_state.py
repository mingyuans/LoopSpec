"""Change-level state and plan.yaml persistence; the open and active Plan are derived."""

from __future__ import annotations

import os
import re
import stat
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from pydantic import ValidationError

from .errors import WorkflowError
from .workflow_io import ResourceBundle, directory, exists, relative_path, write_yaml
from .workflow_models import CHANGE_RE, PLAN_RE, ChangeState, PlanDocument, PlanSpec
from .workflow_planning import load_config, spec_digest
from .workflow_yaml import parse_yaml

STATE_FILE = ".workflow.yaml"


def now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def check_change_name(name: str) -> str:
    if not re.fullmatch(CHANGE_RE, name):
        raise WorkflowError("invalid_change_name", "需求标识必须为安全的字母、数字、下划线或连字符")
    return name


def check_plan_id(value: str) -> str:
    if not re.fullmatch(PLAN_RE, value):
        raise WorkflowError("invalid_plan", "Plan 编号必须是三位数字，例如 001")
    return value


def plan_path(plan_id: str, name: str = "plan.yaml") -> str:
    return f"plans/{check_plan_id(plan_id)}/{name}"


def changes_dir(home: Path) -> str:
    return relative_path(load_config(home).artifacts_dir)


def change_root(home: Path, name: str) -> Path:
    check_change_name(name)
    parent = changes_dir(home)
    try:
        with directory(home, parent + "/" + name):
            pass
    except WorkflowError as exc:
        if isinstance(exc.__cause__, FileNotFoundError):
            raise WorkflowError(
                "change_not_found", "需求不存在", "先执行 loopspec change new <change>。"
            ) from exc
        raise
    return home / parent / name


def read_state(root: Path) -> ChangeState:
    try:
        document = parse_yaml(ResourceBundle(root).read(STATE_FILE))
    except WorkflowError as exc:
        if isinstance(exc.__cause__, FileNotFoundError):
            raise WorkflowError(
                "unsupported_format",
                "需求目录缺少 .workflow.yaml",
                "用 loopspec change new 重新建立需求。",
            ) from exc
        raise
    except (ValueError, UnicodeError) as exc:
        raise WorkflowError("workflow_invalid", "需求元数据不合法") from exc
    if "schema" in document or document.get("format_version") != 4:
        raise WorkflowError(
            "unsupported_format",
            "这是旧格式的需求，2.0 不再执行",
            "用 loopspec v1.x 完成并归档它；或用 loopspec change new 重新建立需求并规划。",
        )
    try:
        state = ChangeState.model_validate(document)
    except ValidationError as exc:
        raise WorkflowError("workflow_invalid", "需求元数据不合法") from exc
    if state.change_name != root.name:
        raise WorkflowError("workflow_invalid", "需求元数据与目录名不一致")
    return state


def write_state(root: Path, state: ChangeState, *, exclusive: bool = False) -> None:
    write_yaml(root, STATE_FILE, state.model_dump(), exclusive=exclusive)


def read_plan(root: Path, plan_id: str) -> PlanDocument:
    try:
        document = ResourceBundle(root).model(plan_path(plan_id), PlanDocument)
    except WorkflowError as exc:
        if isinstance(exc.__cause__, FileNotFoundError):
            raise WorkflowError(
                "plan_not_found", "Plan 不存在", "用 plan list 查看已有 Plan。"
            ) from exc
        if exc.code == "workflow_invalid":
            raise WorkflowError(
                "plan_integrity", "plan.yaml 结构不合法", "不要手改 plan.yaml；用 plan 命令修改。"
            ) from exc
        raise
    if document.meta.plan != plan_id or spec_digest(document.spec) != document.meta.digest:
        raise WorkflowError(
            "plan_integrity",
            "plan.yaml 的 spec 与摘要不一致",
            "不要手改 plan.yaml；从 Git 历史恢复，或归档该 Plan 后重新规划。",
        )
    return document


def write_plan(root: Path, document: PlanDocument) -> None:
    data = {
        "meta": document.meta.model_dump(),
        "spec": document.spec.model_dump(by_alias=True, exclude_none=True),
    }
    write_yaml(root, plan_path(document.meta.plan), data)


def plan_ids(root: Path) -> list[str]:
    try:
        with directory(root, "plans") as fd:
            names = os.listdir(fd)
            if len(names) > 1024:
                raise WorkflowError("resource_limit", "Plan 数量超过限制")
            result = []
            for name in sorted(names):
                if not re.fullmatch(PLAN_RE, name):
                    continue
                info = os.stat(name, dir_fd=fd, follow_symlinks=False)
                if not stat.S_ISDIR(info.st_mode):
                    raise WorkflowError("unsafe_path", "Plan 目录不能是链接或普通文件")
                result.append(name)
    except WorkflowError as exc:
        if isinstance(exc.__cause__, FileNotFoundError):
            return []
        raise
    return [plan_id for plan_id in result if exists(root, plan_path(plan_id))]


@dataclass
class ChangeContext:
    home: Path
    name: str
    root: Path
    state: ChangeState
    _documents: dict[str, PlanDocument] | None = None

    def documents(self) -> dict[str, PlanDocument]:
        if self._documents is None:
            self._documents = {
                plan_id: read_plan(self.root, plan_id) for plan_id in plan_ids(self.root)
            }
        return self._documents

    def open_plan(self) -> str | None:
        """The one draft or approved Plan, if any."""
        found = [
            plan_id
            for plan_id, document in self.documents().items()
            if document.meta.status != "archived"
        ]
        if len(found) > 1:
            raise WorkflowError(
                "history_integrity",
                "同一需求存在多份未结束的 Plan",
                "只能保留一份 draft 或 approved Plan；请人核对 plans/ 后处理。",
            )
        return found[0] if found else None

    def active_plan(self) -> str | None:
        open_plan = self.open_plan()
        if open_plan and self.documents()[open_plan].meta.status == "approved":
            return open_plan
        return None

    def next_plan(self) -> str:
        number = max((int(plan_id) for plan_id in self.documents()), default=0) + 1
        if number > 999:
            raise WorkflowError("resource_limit", "Plan 编号已用尽")
        return f"{number:03d}"


def open_change(home: Path, name: str) -> ChangeContext:
    root = change_root(home, name)
    return ChangeContext(home, name, root, read_state(root))


@dataclass
class LoadedPlan:
    change: ChangeContext
    plan_id: str
    document: PlanDocument

    @property
    def root(self) -> Path:
        """Runtime root: artifacts, evidence and rework records all live in the Plan directory."""
        return self.change.root / "plans" / self.plan_id

    @property
    def spec(self) -> PlanSpec:
        return self.document.spec

    @property
    def digest(self) -> str:
        return self.document.meta.digest

    @property
    def name(self) -> str:
        return self.change.name

    @property
    def home(self) -> Path:
        return self.change.home


def not_active(ctx: ChangeContext) -> WorkflowError:
    open_plan = ctx.open_plan()
    if open_plan is None:
        fix = f"先为完整任务编写请求，执行 loopspec plan create -c {ctx.name} -f <请求文件>。"
    else:
        fix = (
            f"执行 loopspec plan show -c {ctx.name} -p {open_plan} 展示给人，"
            "人确认后再 plan approve。"
        )
    return WorkflowError("plan_not_active", "需求没有已确认的活动 Plan", fix)


def active_plan(ctx: ChangeContext, plan_id: str | None = None) -> LoadedPlan:
    """The only Plan execution commands may touch."""
    active = ctx.active_plan()
    if active is None:
        raise not_active(ctx)
    if plan_id is not None and check_plan_id(plan_id) != active:
        raise WorkflowError(
            "plan_not_active", "指定的 Plan 不是活动 Plan", f"活动 Plan 为 {active}。"
        )
    return LoadedPlan(ctx, active, ctx.documents()[active])
