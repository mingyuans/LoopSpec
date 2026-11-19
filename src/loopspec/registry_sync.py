"""Registry 同步：`registry update` 生成计划，`registry apply` 只更新 `registry.lock.yaml`。

registry 的 fragments/profiles 存放在全局存储（见 `registry_store`），项目内只保留
lock。`update` 从 git 读取目标版本、物化快照并与当前 lock 对比，计划写在
`<home>/.cache/registry/plan.json`（自带 `.gitignore`）；`apply` 在全部预检通过后
才写 lock。两者与 registry 模式下的 `profile save` 共用 `<home>/.cache/registry`
的写锁。
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Literal

from pydantic import Field, ValidationError, field_validator

from . import registry_git
from .errors import WorkflowError
from .models import RegistrySpec, check_tag
from .registry_git import Target
from .registry_store import (
    COMMIT_PATTERN,
    HASH_RE,
    LOCK_FILE,
    DefinitionBundle,
    LockFile,
    Pin,
    RegistryLock,
    RegistryLockV1,
    bundle_for,
    conflict_error,
    definition_key,
    is_definition_file,
    local_conflicts,
    lock_bytes,
    materialize,
    owning_key,
    read_lock,
    read_remote,
    same_source,
)
from .workflow_io import (
    MAX_FILE_BYTES,
    ResourceBundle,
    atomic_write,
    byte_hash,
    canonical,
    digest,
    directory,
    exists,
    read_bytes,
    unlink_file,
    write_json,
    write_lock,
)
from .workflow_models import AssuranceRules, StrictModel

CACHE = ".cache/registry"
PLAN_FILE = CACHE + "/plan.json"
STALE_FIX = "重新运行 loopspec registry update，并基于新的计划确认。"
Status = Literal["added", "modified", "deleted"]


# --------------------------------------------------------------------- models


class PlanEntry(StrictModel):
    path: str
    status: Status
    base: str | None = Field(default=None, pattern=HASH_RE)
    upstream: str | None = Field(default=None, pattern=HASH_RE)

    @field_validator("path")
    @classmethod
    def definition_file(cls, value: str) -> str:
        if not is_definition_file(value):
            raise ValueError("计划条目路径不合法")
        return value


class StoredPlan(StrictModel):
    schema_version: Literal[2] = Field(default=2, alias="schema")
    plan_id: str = Field(pattern=HASH_RE)
    registry: RegistrySpec
    base: str | None = Field(default=None, pattern=HASH_RE)
    upstream_commit: str = Field(pattern=COMMIT_PATTERN)
    upstream_tag: str | None = None
    migration: bool = False
    files: dict[str, str] = Field(max_length=registry_git.MAX_FILES)
    entries: list[PlanEntry] = Field(max_length=2 * registry_git.MAX_FILES)

    @field_validator("upstream_tag")
    @classmethod
    def valid_tag(cls, value: str | None) -> str | None:
        return None if value is None else check_tag(value)

    @field_validator("files")
    @classmethod
    def valid_files(cls, value: dict[str, str]) -> dict[str, str]:
        for path, hashed in value.items():
            if not is_definition_file(path) or len(hashed) != 64:
                raise ValueError("files 条目不合法")
        return value


# ---------------------------------------------------------------- utilities


def _spec(home: Path) -> RegistrySpec:
    from .workflow_planning import load_config

    spec = load_config(home).registry
    if spec is None:
        raise WorkflowError(
            "registry_not_configured",
            "config.yaml 未配置 registry",
            "在 config.yaml 中添加 registry.url（可选 version、path）。",
        )
    return spec


def _prepare_cache(home: Path) -> None:
    with directory(home, CACHE, create=True):
        pass
    if not exists(home, CACHE + "/.gitignore"):
        atomic_write(home, CACHE + "/.gitignore", b"*\n")


@contextmanager
def registry_write_lock(home: Path) -> Iterator[None]:
    """The project-level lock shared by update, apply and registry-mode profile save."""
    _prepare_cache(home)
    with write_lock(home / CACHE):
        yield


def _base_hash(found: LockFile | None) -> str | None:
    return found.raw_hash if found else None


def _remove_plan(home: Path) -> None:
    try:
        unlink_file(home, PLAN_FILE)
    except WorkflowError:
        pass


def _up_to_date(home: Path, spec: RegistrySpec, lock: RegistryLock) -> dict:
    _remove_plan(home)
    return {
        "registry": spec.model_dump(),
        "upToDate": True,
        "baseCommit": lock.commit,
        "baseTag": lock.tag,
        "upstreamCommit": lock.commit,
        "upstreamTag": lock.tag,
        "baseAvailable": True,
        "migration": False,
        "sourceChanged": False,
        "previousRegistry": None,
        "planId": None,
        "definitions": [],
        "files": [],
        "localConflicts": local_conflicts(home, {definition_key(p) for p in lock.files}),
        "brokenReferences": [],
        "warnings": [],
        "nextSteps": [],
    }


def _plan_references(home: Path) -> dict[str, list[str]]:
    """Definition files referenced by the approved Plans of open changes, by change."""
    from .workflow_state import changes_dir, open_change

    references: dict[str, list[str]] = {}
    try:
        parent = home / changes_dir(home)
    except WorkflowError:
        return references
    if not parent.is_dir() or parent.is_symlink():
        return references
    for name in sorted(os.listdir(parent)):
        try:
            ctx = open_change(home, name)
            plan_id = ctx.active_plan()
            if plan_id is None:
                continue
            nodes = ctx.documents()[plan_id].spec.nodes
        except WorkflowError:
            continue
        paths: set[str] = set()
        for node in nodes:
            paths.update(p for p in (node.instruction, node.template) if p)
            if node.gate:
                if node.gate.assurance:
                    paths.add(node.gate.assurance)
                if node.gate.templates:
                    paths.update((node.gate.templates.pass_, node.gate.templates.fail))
        references[name] = sorted(paths)
    return references


def _broken_references(home: Path, files: dict[str, str]) -> list[dict]:
    """Active Plan resources that the given registry file table would no longer provide."""
    keys = {definition_key(path) for path in files}
    broken = []
    for change, paths in _plan_references(home).items():
        for path in paths:
            key = owning_key(path)
            if key is None:
                continue
            if key in keys:
                if path not in files:
                    broken.append({"change": change, "path": path})
            elif not os.path.lexists(home / path):
                broken.append({"change": change, "path": path})
    return broken


def _definition_errors(bundle: DefinitionBundle) -> list[tuple[str, WorkflowError]]:
    return _definition_errors_with(bundle)


def _definition_errors_with(bundle: ResourceBundle) -> list[tuple[str, WorkflowError]]:
    from .workflow_catalog import WorkflowCatalog
    from .workflow_compiler import FragmentExpander
    from .workflow_planning import validate_profile

    errors: list[tuple[str, WorkflowError]] = []
    try:
        names = WorkflowCatalog(bundle.root, bundle)
        listed = {kind: names.names(kind) for kind in ("fragments", "profiles")}
    except WorkflowError as exc:
        return [("catalog", exc)]
    for kind in ("fragments", "profiles"):
        for name in listed[kind]:
            catalog = WorkflowCatalog(bundle.root, bundle)
            try:
                if kind == "fragments":
                    expanded = FragmentExpander(catalog)
                    expanded.expand(name, "fragment")
                    expanded.connect()
                    expanded.validate()
                    for node in expanded.resolve_nodes():
                        for path in (node.instruction, node.template):
                            if path:
                                bundle.read(path).decode("utf-8")
                else:
                    validate_profile(catalog, catalog.profile(name))
            except UnicodeError:
                error = WorkflowError("workflow_invalid", "资源文件不是 UTF-8 文本")
                errors.append((f"{kind}/{name}", error))
            except WorkflowError as exc:
                errors.append((f"{kind}/{name}", exc))
    return errors


def _new_errors(
    home: Path, bundle: DefinitionBundle, errors: list[tuple[str, WorkflowError]]
) -> list[tuple[str, WorkflowError]]:
    """Drop errors of local definitions that were already broken before this sync."""
    from .registry_store import definition_bundle

    local = [item for item in errors if item[0] not in bundle.registry_keys]
    if not local:
        return errors
    try:
        before: ResourceBundle = definition_bundle(home)
    except WorkflowError:
        before = ResourceBundle(home)
    previous = {key for key, _ in _definition_errors_with(before)}
    return [item for item in errors if item[0] in bundle.registry_keys or item[0] not in previous]


def _project_error(bundle: DefinitionBundle) -> WorkflowError | None:
    from .workflow_catalog import WorkflowCatalog
    from .workflow_planning import project_constraints

    try:
        project = project_constraints(bundle.root)
        available = set(WorkflowCatalog(bundle.root, bundle).names("fragments"))
        if not set(project.required_fragments) <= available:
            return WorkflowError(
                "project_constraint",
                "同步后缺少 config.yaml workflow.required_fragments 要求的 Fragment",
                "在 registry 中保留这些 Fragment，或调整 config.yaml 后重试。",
            )
        if project.assurance_rules:
            bundle.model(project.assurance_rules, AssuranceRules)
    except WorkflowError as exc:
        return exc
    return None


# --------------------------------------------------------------------- update


def update(home: Path, *, full: bool = False) -> dict:
    spec = _spec(home)
    with registry_write_lock(home):
        found = read_lock(home)
        lock = found.lock if found else None
        current = (
            isinstance(lock, RegistryLock) and same_source(spec, lock.registry) and not full
        )
        if current and isinstance(lock, RegistryLock):
            if spec.version != "latest" and lock.tag == spec.version:
                return _up_to_date(home, spec, lock)

        def same_target(target: Target) -> bool:
            # Both the commit and the tag: a re-pinned tag on the same commit still needs
            # a new lock, or pinned() would refuse the project.
            return (
                current
                and isinstance(lock, RegistryLock)
                and target.commit == lock.commit
                and target.tag == lock.tag
            )

        def fetch(repo: registry_git.RegistryRepo) -> tuple[Target, registry_git.RemoteTree]:
            target = repo.resolve_target()
            if same_target(target):
                return target, registry_git.RemoteTree()
            repo.fetch(target)
            return target, repo.read_tree(target.commit)

        target, tree = read_remote(spec, fetch)
        if same_target(target) and isinstance(lock, RegistryLock):
            return _up_to_date(home, spec, lock)
        upstream = {path: byte_hash(data) for path, data in tree.files.items()}
        snapshot = materialize(spec, target.commit, target.tag, upstream, tree.files)
        return _build_plan(home, spec, found, target, upstream, snapshot, list(tree.warnings))


def _build_plan(
    home: Path,
    spec: RegistrySpec,
    found: LockFile | None,
    target: Target,
    upstream: dict[str, str],
    snapshot: Path,
    warnings: list[str],
) -> dict:
    lock = found.lock if found else None
    same = lock is not None and same_source(spec, lock.registry)
    base: dict[str, str] = dict(lock.files) if lock is not None else {}
    if lock is not None and not same:
        warnings.append(
            "registry 来源（url/path）与 registry.lock.yaml 不一致：见 previousRegistry，"
            "来源切换本身需要单独确认，即使文件内容没有变化"
        )
    base_snapshot: Path | None = None
    if lock is not None and same and not (isinstance(lock, RegistryLockV1) and lock.held):
        try:
            base_snapshot = materialize(spec, lock.commit, lock.tag, dict(lock.files))
        except WorkflowError:
            base_snapshot = None
    base_available = lock is None or base_snapshot is not None
    entries: list[PlanEntry] = []
    for path in sorted(set(base) | set(upstream)):
        old, new = base.get(path), upstream.get(path)
        if old == new:
            continue
        status: Status = "added" if old is None else "deleted" if new is None else "modified"
        entries.append(PlanEntry(path=path, status=status, base=old, upstream=new))
    if entries and lock is not None and not base_available:
        warnings.append("无法取得当前 lock 版本的内容，修改与删除的文件只能对比 hash")
    migration = isinstance(lock, RegistryLockV1)
    if migration:
        warnings.append(
            "registry.lock.yaml 是旧格式：apply 后改写为新格式，定义不再写入项目目录，"
            "项目内与 registry 同名的定义需要先删除"
        )
    body = {
        "schema": 2,
        "registry": spec.model_dump(),
        "base": _base_hash(found),
        "upstream_commit": target.commit,
        "upstream_tag": target.tag,
        "migration": migration,
        "files": upstream,
        "entries": [e.model_dump() for e in entries],
    }
    plan = StoredPlan.model_validate({"plan_id": digest(body), **body})
    # The lock apply would write must stay readable, or the plan could never be applied.
    lock_bytes(
        RegistryLock(registry=spec, commit=target.commit, tag=target.tag, files=upstream)
    )
    if len(canonical(plan.model_dump(by_alias=True))) > MAX_FILE_BYTES:
        raise WorkflowError("resource_limit", "registry 同步计划超过大小限额")
    write_json(home, PLAN_FILE, plan.model_dump(by_alias=True))
    files = [
        {
            "path": item.path,
            "status": item.status,
            "upstreamPath": str(snapshot / item.path) if item.upstream else None,
            "basePath": str(base_snapshot / item.path)
            if base_snapshot is not None and item.base
            else None,
        }
        for item in entries
    ]
    upstream_keys = {definition_key(p) for p in upstream}
    base_keys = {definition_key(p) for p in base}
    definitions = []
    for key in sorted({definition_key(e.path) for e in entries}):
        kind, name = key.split("/")
        if key not in base_keys:
            change = "added"
        elif key not in upstream_keys:
            change = "deleted"
        else:
            change = "modified"
        definitions.append({"kind": kind[:-1], "name": name, "change": change})
    return {
        "registry": spec.model_dump(),
        "upToDate": False,
        "baseCommit": lock.commit if lock else None,
        "baseTag": lock.tag if lock else None,
        "upstreamCommit": target.commit,
        "upstreamTag": target.tag,
        "baseAvailable": base_available,
        "migration": migration,
        "sourceChanged": lock is not None and not same,
        "previousRegistry": lock.registry.model_dump() if lock is not None and not same else None,
        "planId": plan.plan_id,
        "definitions": definitions,
        "files": files,
        "localConflicts": local_conflicts(home, upstream_keys),
        "brokenReferences": _broken_references(home, upstream),
        "warnings": warnings,
        "nextSteps": [f"loopspec registry apply --plan {plan.plan_id}"],
    }


# ---------------------------------------------------------------------- apply


def _stale(message: str) -> WorkflowError:
    return WorkflowError("registry_plan_stale", message, STALE_FIX)


def _load_plan(home: Path) -> StoredPlan:
    try:
        raw = read_bytes(home, PLAN_FILE)
    except WorkflowError as exc:
        raise _stale("没有可应用的 registry 计划") from exc
    try:
        plan = StoredPlan.model_validate(json.loads(raw))
    except (ValueError, ValidationError, RecursionError) as exc:
        raise _stale("registry 计划已损坏") from exc
    body = plan.model_dump(by_alias=True)
    plan_id = body.pop("plan_id")
    if digest(body) != plan_id:
        raise _stale("registry 计划已损坏")
    return plan


def apply(home: Path, plan_id: str) -> dict:
    spec = _spec(home)
    with registry_write_lock(home):
        plan = _load_plan(home)
        # Compared for equality only; the id never becomes part of a path from user input.
        if plan_id != plan.plan_id:
            raise _stale("计划 ID 与最新的 registry update 结果不一致")
        if plan.registry != spec:
            raise _stale("计划生成后 config.yaml 的 registry 已改变")
        if _base_hash(read_lock(home)) != plan.base:
            raise _stale("计划生成后 registry.lock.yaml 已被修改")
        lock = RegistryLock(
            registry=spec, commit=plan.upstream_commit, tag=plan.upstream_tag, files=plan.files
        )
        data = lock_bytes(lock)
        pin = Pin(spec, lock.commit, lock.tag, dict(lock.files), byte_hash(data))
        conflicts = local_conflicts(home, pin.keys)
        if conflicts:
            raise conflict_error(conflicts)
        snapshot = materialize(spec, plan.upstream_commit, plan.upstream_tag, plan.files)
        bundle = bundle_for(home, pin, snapshot=snapshot)
        errors = _definition_errors(bundle)
        if errors:
            errors = _new_errors(home, bundle, errors)
        if errors:
            key, error = errors[0]
            raise WorkflowError(
                error.code,
                f"同步结果中的 {key} 校验失败：{error.message}",
                "在 registry 中修复该定义（或修复项目内的本地定义）后重新 update。",
            ) from error
        project = _project_error(bundle)
        if project is not None:
            raise WorkflowError(
                project.code, f"同步后项目配置无法满足：{project.message}", project.fix
            ) from project
        broken = _broken_references(home, plan.files)
        if broken:
            listed = "、".join(f"{item['change']}:{item['path']}" for item in broken)
            raise WorkflowError(
                "registry_breaks_running_plan",
                "同步会删除进行中 Plan 引用的资源：" + listed,
                "先完成或归档这些 change，或在 registry 中保留这些资源后重新 update。",
            )
        atomic_write(home, LOCK_FILE, data)
        _remove_plan(home)
    return {
        "applied": True,
        "upstreamCommit": plan.upstream_commit,
        "upstreamTag": plan.upstream_tag,
        "migration": plan.migration,
        "added": [e.path for e in plan.entries if e.status == "added"],
        "modified": [e.path for e in plan.entries if e.status == "modified"],
        "deleted": [e.path for e in plan.entries if e.status == "deleted"],
        "lock": LOCK_FILE,
        "nextSteps": [],
    }
