"""Registry 同步：锁文件基线、三方分类、`registry update` 计划与 `registry apply` 写入。

`update` 只写 `<home>/.cache/registry/`；`apply` 在全部校验通过后才写入
`fragments/`、`profiles/` 与锁文件。版本只记录在锁文件中（按定义），
Fragment / Profile 自身的格式不变。
"""

from __future__ import annotations

import json
import os
import re
import shutil
import stat
from pathlib import Path
from typing import Literal

from pydantic import Field, ValidationError, field_validator, model_validator

from . import registry_git
from .errors import WorkflowError
from .models import RegistrySpec, check_tag
from .registry_git import RegistryRepo, Target, safe_segments
from .workflow_catalog import WorkflowCatalog
from .workflow_compiler import FragmentExpander
from .workflow_io import (
    ResourceBundle,
    atomic_write,
    byte_hash,
    digest,
    directory,
    exists,
    read_bytes,
    relative_path,
    unlink_file,
    write_json,
    write_lock,
    write_yaml,
)
from .workflow_models import StrictModel
from .workflow_planning import load_config, validate_profile

LOCK_FILE = "registry.lock.yaml"
CACHE = ".cache/registry"
PLAN_FILE = CACHE + "/plan.json"
HASH_RE = r"^[0-9a-f]{64}$"
_NAME = r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*"
_SEGMENT = r"[A-Za-z0-9._-]+"
FILE_RE = re.compile(rf"^(fragments/{_NAME}(?:/{_SEGMENT})+|profiles/{_NAME}\.yaml)$")
DEFINITION_RE = re.compile(rf"^(fragments|profiles)/({_NAME})$")
PENDING = {"upstream-modified", "upstream-added", "upstream-deleted"}
STALE_FIX = "重新运行 loopspec registry update，并基于新的计划确认。"
Status = Literal[
    "unchanged",
    "upstream-modified",
    "upstream-added",
    "upstream-deleted",
    "local-modified",
    "local-deleted",
    "local-only",
    "conflict",
]


# --------------------------------------------------------------------- models


class DefinitionVersion(StrictModel):
    tag: str | None = None
    commit: str = Field(pattern=r"^([0-9a-f]{40}|[0-9a-f]{64})$")

    @field_validator("tag")
    @classmethod
    def valid_tag(cls, value: str | None) -> str | None:
        return None if value is None else check_tag(value)


class RegistryLock(StrictModel):
    """`<home>/registry.lock.yaml`: what the last apply synced, committed with the project."""

    version: Literal[1] = 1
    registry: RegistrySpec
    commit: str = Field(pattern=r"^([0-9a-f]{40}|[0-9a-f]{64})$")
    tag: str | None = None
    definitions: dict[str, DefinitionVersion] = Field(default_factory=dict, max_length=4096)
    # Definitions with a skipped file: they keep the next update from reporting up to date.
    held: list[str] = Field(default_factory=list, max_length=4096)
    files: dict[str, str] = Field(default_factory=dict, max_length=8192)

    @field_validator("tag")
    @classmethod
    def valid_tag(cls, value: str | None) -> str | None:
        return None if value is None else check_tag(value)

    @model_validator(mode="after")
    def valid_keys(self) -> RegistryLock:
        for key in [*self.definitions, *self.held]:
            if not DEFINITION_RE.fullmatch(key):
                raise ValueError("definitions / held 键不合法")
        for path, value in self.files.items():
            if not is_definition_file(path) or not re.fullmatch(HASH_RE, value):
                raise ValueError("files 条目不合法")
            relative_path(path)
        return self


class PlanEntry(StrictModel):
    path: str
    status: Status
    base: str | None = Field(default=None, pattern=HASH_RE)
    local: str | None = Field(default=None, pattern=HASH_RE)
    upstream: str | None = Field(default=None, pattern=HASH_RE)

    @field_validator("path")
    @classmethod
    def definition_file(cls, value: str) -> str:
        if not is_definition_file(value):
            raise ValueError("计划条目路径不合法")
        return value


class StoredPlan(StrictModel):
    plan_id: str = Field(pattern=HASH_RE)
    registry: RegistrySpec
    upstream_commit: str
    upstream_tag: str | None = None
    entries: list[PlanEntry]


# ---------------------------------------------------------------- utilities


def is_definition_file(path: str) -> bool:
    """A file of a fragment directory or a profile, with shell-safe path segments."""
    if not FILE_RE.fullmatch(path) or not safe_segments(path):
        return False
    try:
        relative_path(path)
    except WorkflowError:
        return False
    return True


def definition_key(path: str) -> str:
    parts = path.split("/")
    return f"fragments/{parts[1]}" if parts[0] == "fragments" else f"profiles/{parts[1][:-5]}"


def _spec(home: Path) -> RegistrySpec:
    spec = load_config(home).registry
    if spec is None:
        raise WorkflowError(
            "registry_not_configured",
            "config.yaml 未配置 registry",
            "在 config.yaml 中添加 registry.url（可选 version、path）。",
        )
    return spec


def read_lock(home: Path) -> RegistryLock | None:
    try:
        return ResourceBundle(home).model(LOCK_FILE, RegistryLock)
    except WorkflowError as exc:
        if isinstance(exc.__cause__, FileNotFoundError) or (
            exc.__cause__ is not None and isinstance(exc.__cause__.__cause__, FileNotFoundError)
        ):
            return None
        if exc.code in ("workflow_invalid", "resource_limit"):
            raise WorkflowError(
                "config_invalid",
                "registry.lock.yaml 结构不合法",
                "从版本库恢复 registry.lock.yaml，或删除它后重新同步（所有差异将作为冲突出现）。",
            ) from exc
        if exc.code == "unsafe_path" and not os.path.lexists(home / LOCK_FILE):
            return None
        raise


def synced_versions(home: Path) -> dict[str, dict[str, str | None]]:
    """Per-definition sync source for `fragment list`/`profile list`; never fails."""
    try:
        lock = read_lock(home)
    except Exception:  # noqa: BLE001 - listing must not fail on a broken lock
        return {}
    if lock is None:
        return {}
    return {
        key: {"syncedTag": value.tag, "syncedCommit": value.commit}
        for key, value in lock.definitions.items()
    }


def _same_source(lock: RegistryLock, spec: RegistrySpec) -> bool:
    return lock.registry.url == spec.url and lock.registry.path == spec.path


def _prepare_cache(home: Path) -> None:
    with directory(home, CACHE, create=True):
        pass
    if not exists(home, CACHE + "/.gitignore"):
        atomic_write(home, CACHE + "/.gitignore", b"*\n")


def _remove(home: Path, path: str) -> None:
    """Remove a cache subtree; refuses to follow a link planted in its place."""
    target = home / relative_path(path)
    try:
        info = os.lstat(target)
    except FileNotFoundError:
        return
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
        raise WorkflowError("unsafe_path", "缓存目录不是普通目录")
    shutil.rmtree(target)


def _local_hash(home: Path, path: str) -> str | None:
    try:
        return byte_hash(read_bytes(home, path))
    except WorkflowError as exc:
        if isinstance(exc.__cause__, FileNotFoundError):
            return None
        raise


def _scan_local(home: Path, keys: set[str]) -> tuple[dict[str, str], list[str], int]:
    """Hashes of local files of the given definitions, unsupported entries, invalid names."""
    files: dict[str, str] = {}
    unsupported: list[str] = []
    invalid = 0

    def visit(path: str, depth: int) -> None:
        nonlocal invalid
        if depth > registry_git.MAX_DEPTH:
            unsupported.append(path)
            return
        with directory(home, path) as fd:
            names = sorted(os.listdir(fd))
            if len(files) + len(names) > registry_git.MAX_FILES * 2:
                raise WorkflowError("resource_limit", "本地定义文件过多")
            for name in names:
                child = path + "/" + name
                if not safe_segments(name):
                    # Never echoed: the name itself may carry shell or bidi text.
                    invalid += 1
                    continue
                info = os.stat(name, dir_fd=fd, follow_symlinks=False)
                if stat.S_ISDIR(info.st_mode):
                    visit(child, depth + 1)
                elif stat.S_ISREG(info.st_mode):
                    files[child] = byte_hash(read_bytes(home, child))
                else:
                    unsupported.append(child)

    for key in sorted(keys):
        kind, name = key.split("/")
        if kind == "profiles":
            path = f"profiles/{name}.yaml"
            try:
                info = os.lstat(home / path)
            except FileNotFoundError:
                continue
            if stat.S_ISREG(info.st_mode):
                files[path] = byte_hash(read_bytes(home, path))
            else:
                unsupported.append(path)
            continue
        try:
            info = os.lstat(home / key)
        except FileNotFoundError:
            continue
        if not stat.S_ISDIR(info.st_mode):
            unsupported.append(key)
            continue
        visit(key, 1)
    return files, unsupported, invalid


def classify(base: str | None, local: str | None, upstream: str | None) -> Status:
    if local == upstream:
        return "unchanged"
    if base is not None:
        if local == base:
            return "upstream-deleted" if upstream is None else "upstream-modified"
        if upstream == base:
            return "local-deleted" if local is None else "local-modified"
        return "conflict"
    if local is None:
        return "upstream-added"
    if upstream is None:
        return "local-only"
    return "conflict"


# --------------------------------------------------------------------- update


def update(home: Path, *, full: bool = False) -> dict:
    spec = _spec(home)
    lock = read_lock(home)
    same = lock is not None and _same_source(lock, spec)
    behind = lock is not None and (
        bool(lock.held) or any(v.commit != lock.commit for v in lock.definitions.values())
    )
    current = same and not behind and not full
    if current and lock is not None and spec.version != "latest" and lock.tag == spec.version:
        return _up_to_date(home, spec, lock)
    _prepare_cache(home)
    with write_lock(home / CACHE):
        repo = RegistryRepo(home / CACHE, spec)
        target = repo.resolve_target()
        if current and lock is not None and target.commit == lock.commit:
            return _up_to_date(home, spec, lock)
        repo.fetch(target)
        tree = repo.read_tree(target.commit)
        warnings = list(tree.warnings)
        base_files: dict[str, bytes] = {}
        base_available = False
        if lock is not None:
            if not same:
                warnings.append(
                    "registry 来源（url/path）与锁文件不一致：不使用旧基线，"
                    "所有差异按冲突处理，不会规划任何删除"
                )
            elif repo.fetch_base(lock.commit, lock.tag):
                try:
                    base_files = repo.read_tree(lock.commit).files
                    base_available = True
                except WorkflowError:
                    base_available = False
        return _build_plan(home, spec, lock, target, tree, base_files, base_available, warnings)


def _up_to_date(home: Path, spec: RegistrySpec, lock: RegistryLock) -> dict:
    try:
        unlink_file(home, PLAN_FILE)
    except WorkflowError:
        pass
    return {
        "registry": spec.model_dump(),
        "upToDate": True,
        "baseCommit": lock.commit,
        "baseTag": lock.tag,
        "upstreamCommit": lock.commit,
        "upstreamTag": lock.tag,
        "baseAvailable": True,
        "planId": None,
        "definitions": [],
        "files": [],
        "unsupported": [],
        "warnings": [],
        "nextSteps": [],
    }


def _build_plan(
    home: Path,
    spec: RegistrySpec,
    lock: RegistryLock | None,
    target: Target,
    tree: registry_git.RemoteTree,
    base_files: dict[str, bytes],
    base_available: bool,
    warnings: list[str],
) -> dict:
    upstream = {path: byte_hash(data) for path, data in tree.files.items()}
    # A different source shares no history with the lock: using its hashes as the base
    # would turn every file of the old registry into a confirmed-looking deletion.
    same = lock is not None and _same_source(lock, spec)
    base = dict(lock.files) if lock and same else {}
    keys = {definition_key(p) for p in upstream} | {definition_key(p) for p in base}
    if lock:
        keys |= set(lock.definitions)
    local, local_unsupported, invalid = _scan_local(home, keys)
    if invalid:
        warnings = [*warnings, f"本地有 {invalid} 个名称不合法的文件已忽略"]
    blocked = set(tree.unsupported) | set(local_unsupported)

    def is_blocked(path: str) -> bool:
        return any(path == b or path.startswith(b + "/") for b in blocked)

    entries = []
    for path in sorted(set(upstream) | set(base) | set(local)):
        if is_blocked(path):
            continue
        status = classify(base.get(path), local.get(path), upstream.get(path))
        entries.append(
            PlanEntry(
                path=path,
                status=status,
                base=base.get(path),
                local=local.get(path),
                upstream=upstream.get(path),
            )
        )
    body = {
        "registry": spec.model_dump(),
        "upstream_commit": target.commit,
        "upstream_tag": target.tag,
        "entries": [e.model_dump() for e in entries],
    }
    plan = StoredPlan.model_validate({"plan_id": digest(body), **body})
    _remove(home, CACHE + "/staging")
    staging = f"{CACHE}/staging/{plan.plan_id}"
    listed = []
    for item in entries:
        if item.status == "unchanged":
            continue
        upstream_path = base_path = None
        if item.upstream is not None and item.status in PENDING | {"conflict"}:
            atomic_write(home, f"{staging}/upstream/{item.path}", tree.files[item.path])
            upstream_path = str((home / staging / "upstream" / item.path).absolute())
        content = base_files.get(item.path)
        if (
            item.status in PENDING | {"conflict"}
            and content is not None
            and byte_hash(content) == item.base
        ):
            atomic_write(home, f"{staging}/base/{item.path}", content)
            base_path = str((home / staging / "base" / item.path).absolute())
        listed.append(
            {
                "path": item.path,
                "status": item.status,
                "localPath": str((home / item.path).absolute()),
                "upstreamPath": upstream_path,
                "basePath": base_path,
            }
        )
    write_json(home, PLAN_FILE, plan.model_dump())
    upstream_keys = {definition_key(p) for p in upstream}
    definitions = []
    for key in sorted(keys):
        kind, name = key.split("/")
        recorded = lock.definitions.get(key) if lock and same else None
        present = key in upstream_keys
        if not present and recorded is None:
            continue
        definitions.append(
            {
                "kind": kind[:-1],
                "name": name,
                "deletedUpstream": not present,
                "baseTag": recorded.tag if recorded else None,
                "baseCommit": recorded.commit if recorded else None,
                "upstreamTag": target.tag if present else None,
                "upstreamCommit": target.commit if present else None,
            }
        )
    return {
        "registry": spec.model_dump(),
        "upToDate": False,
        "baseCommit": lock.commit if lock else None,
        "baseTag": lock.tag if lock else None,
        "upstreamCommit": target.commit,
        "upstreamTag": target.tag,
        "baseAvailable": base_available,
        "planId": plan.plan_id,
        "definitions": definitions,
        "files": listed,
        "unsupported": sorted(blocked),
        "warnings": warnings,
        "nextSteps": [
            f"loopspec registry apply --plan {plan.plan_id} "
            "[--resolve <path>=local|upstream]... [--skip <path>]..."
        ],
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
    except (ValueError, ValidationError) as exc:
        raise _stale("registry 计划已损坏") from exc
    body = plan.model_dump()
    plan_id = body.pop("plan_id")
    if digest(body) != plan_id:
        raise _stale("registry 计划已损坏")
    return plan


def _parse_resolutions(values: list[str]) -> dict[str, str]:
    resolutions: dict[str, str] = {}
    for value in values:
        path, sep, choice = value.rpartition("=")
        if not sep or choice not in ("local", "upstream"):
            raise WorkflowError("config_invalid", "--resolve 格式应为 <path>=local|upstream")
        path = relative_path(path)
        if path in resolutions:
            raise WorkflowError("config_invalid", "同一路径只能有一个 --resolve")
        resolutions[path] = choice
    return resolutions


def apply(home: Path, plan_id: str, resolve: list[str], skip: list[str]) -> dict:
    spec = _spec(home)
    _prepare_cache(home)
    with write_lock(home / CACHE):
        plan = _load_plan(home)
        # Compared for equality only; the id never becomes part of a path from user input.
        if plan_id != plan.plan_id:
            raise _stale("计划 ID 与最新的 registry update 结果不一致")
        if plan.registry != spec:
            raise _stale("计划生成后 config.yaml 的 registry 已改变")
        resolutions = _parse_resolutions(resolve)
        skipped = {relative_path(path) for path in skip}
        by_path = {e.path: e for e in plan.entries}
        conflicts = {e.path for e in plan.entries if e.status == "conflict"}
        pending = {e.path for e in plan.entries if e.status in PENDING}
        if not set(resolutions) <= conflicts:
            raise WorkflowError("config_invalid", "--resolve 只能指向冲突条目")
        if not skipped <= pending:
            raise WorkflowError("config_invalid", "--skip 只能指向待确认的上游变更")
        if conflicts - set(resolutions):
            raise WorkflowError(
                "registry_conflict_unresolved",
                f"还有 {len(conflicts - set(resolutions))} 个冲突未解决",
                "为每个冲突提供 --resolve <path>=local|upstream。",
            )
        writes: dict[str, bytes | None] = {}
        for item in plan.entries:
            accepted = (item.status in PENDING and item.path not in skipped) or (
                resolutions.get(item.path) == "upstream"
            )
            if resolutions.get(item.path) != "local" and _local_hash(home, item.path) != item.local:
                raise _stale("计划生成后本地文件已被修改")
            if not accepted:
                continue
            if item.upstream is None:
                writes[item.path] = None
                continue
            try:
                data = read_bytes(home, f"{CACHE}/staging/{plan.plan_id}/upstream/{item.path}")
            except WorkflowError as exc:
                raise _stale("计划的暂存内容缺失") from exc
            if byte_hash(data) != item.upstream:
                raise _stale("计划的暂存内容已被修改")
            writes[item.path] = data
        upstream_keys = {definition_key(e.path) for e in plan.entries if e.upstream is not None}
        _validate_preview(home, writes, upstream_keys)
        # Built before any write: an invalid result must leave the workspace untouched.
        lock = _next_lock(home, spec, plan, by_path, skipped)
        written: list[str] = []
        deleted: list[str] = []
        for path, content in sorted(writes.items()):
            if content is None:
                if _local_hash(home, path) is not None:
                    unlink_file(home, path)
                    _prune(home, path)
                deleted.append(path)
            else:
                atomic_write(home, path, content)
                written.append(path)
        write_yaml(home, LOCK_FILE, lock.model_dump())
        _remove(home, CACHE + "/staging")
        _remove(home, CACHE + "/preview")
        unlink_file(home, PLAN_FILE)
    return {
        "applied": True,
        "upstreamCommit": plan.upstream_commit,
        "upstreamTag": plan.upstream_tag,
        "written": written,
        "deleted": deleted,
        "skipped": sorted(skipped),
        "kept": sorted(p for p, choice in resolutions.items() if choice == "local"),
        "lock": LOCK_FILE,
        "nextSteps": [],
    }


def _definition_error(root: Path, key: str) -> WorkflowError | None:
    """Load one definition the way Plans use it; `None` when it is valid."""
    kind, name = key.split("/")
    try:
        if kind == "fragments":
            expanded = FragmentExpander(WorkflowCatalog(root))
            expanded.expand(name, "fragment")
            expanded.connect()
            expanded.validate()
            expanded.resolve_nodes()
        else:
            catalog = WorkflowCatalog(root)
            validate_profile(catalog, catalog.profile(name))
    except WorkflowError as exc:
        return exc
    return None


def _definitions_in(root: Path) -> set[str]:
    keys = set()
    for kind in ("fragments", "profiles"):
        try:
            names = os.listdir(root / kind)
        except FileNotFoundError:
            continue
        for name in names:
            if kind == "fragments" and re.fullmatch(_NAME, name):
                if (root / kind / name / "fragment.yaml").is_file():
                    keys.add(f"fragments/{name}")
            elif kind == "profiles" and name.endswith(".yaml") and re.fullmatch(_NAME, name[:-5]):
                keys.add(f"profiles/{name[:-5]}")
    return keys


def _validate_preview(home: Path, writes: dict[str, bytes | None], keys: set[str]) -> None:
    """Build the resulting fragments/profiles under the cache and load every definition.

    Registry-owned and rewritten definitions must load. Any other local definition
    must not be broken by the sync (for example a local Profile using a Fragment the
    registry deleted); one that was already broken before is left alone.
    """
    preview = CACHE + "/preview"
    _remove(home, preview)
    root = home / preview
    try:
        for kind in ("fragments", "profiles"):
            if os.path.isdir(home / kind) and not os.path.islink(home / kind):
                shutil.copytree(home / kind, root / kind, symlinks=True)
            else:
                (root / kind).mkdir(parents=True, exist_ok=True)
        for path, data in writes.items():
            if data is None:
                try:
                    unlink_file(root, path)
                except WorkflowError:
                    pass
            else:
                atomic_write(root, path, data)
        owned = keys | {definition_key(p) for p in writes}
        for key in sorted(_definitions_in(root)):
            error = _definition_error(root, key)
            if error is None:
                continue
            if key not in owned and _definition_error(home, key) is not None:
                continue
            raise WorkflowError(
                error.code,
                f"同步结果中的 {key} 校验失败：{error.message}",
                "在 registry 中修复该定义，或用 --skip / --resolve 保留本地版本后重试。",
            ) from error
    finally:
        _remove(home, preview)


def _prune(home: Path, path: str) -> None:
    """Remove directories emptied by a deletion, up to and including `fragments/<name>`."""
    parts = path.split("/")
    if parts[0] != "fragments":
        return
    for depth in range(len(parts) - 1, 1, -1):
        parent, name = "/".join(parts[: depth - 1]), parts[depth - 1]
        with directory(home, parent) as fd:
            try:
                os.rmdir(name, dir_fd=fd)
            except OSError:
                return


def _next_lock(
    home: Path,
    spec: RegistrySpec,
    plan: StoredPlan,
    by_path: dict[str, PlanEntry],
    skipped: set[str],
) -> RegistryLock:
    previous = read_lock(home)
    files: dict[str, str] = {}
    for path, item in by_path.items():
        if path in skipped:
            if item.base is not None:
                files[path] = item.base
        elif item.upstream is not None:
            files[path] = item.upstream
    held = {definition_key(p) for p in skipped}
    current = DefinitionVersion(tag=plan.upstream_tag, commit=plan.upstream_commit)
    definitions: dict[str, DefinitionVersion] = {}
    upstream_keys = {definition_key(p) for p, e in by_path.items() if e.upstream is not None}
    old = previous.definitions if previous and _same_source(previous, spec) else {}
    for key in sorted(upstream_keys | held):
        if key in held:
            if key in old:
                definitions[key] = old[key]
        elif key in upstream_keys:
            definitions[key] = current
    return RegistryLock(
        registry=spec,
        commit=plan.upstream_commit,
        tag=plan.upstream_tag,
        definitions=definitions,
        held=sorted(held),
        files=files,
    )
