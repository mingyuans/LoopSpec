"""Registry 全局存储：按来源与 commit 存放不可变快照，项目只保留 `registry.lock.yaml`。

registry 模式下，fragments/profiles 不再写入项目，而是物化到用户级目录
`$LOOPSPEC_REGISTRY_STORE`（默认 `~/.loopspec/registry`）：

    <store>/<source-id>/<commit>/{.snapshot.json, fragments/..., profiles/...}

快照只在有可信文件表（lock 或 apply 计划）时物化或复用：先写临时目录，
再原子 rename 发布；已存在的快照按文件表完整校验，损坏时报错而不自动替换。
读取定义统一经过 `definition_bundle(home)`：registry 定义从快照读并逐文件
按 lock 的 hash 校验，其余路径（本地独有定义、config.yaml）仍从 home 读。
"""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import stat
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, TypeVar

import yaml
from pydantic import Field, ValidationError, field_validator, model_validator

from .errors import WorkflowError
from .models import RegistrySpec, check_tag
from .registry_git import MAX_FILES, RegistryRepo, safe_segments
from .workflow_io import (
    MAX_BUNDLE_BYTES,
    ResourceBundle,
    atomic_write,
    byte_hash,
    canonical,
    directory,
    exists,
    read_bytes,
    relative_path,
)
from .workflow_models import StrictModel
from .workflow_yaml import MAX_DOCUMENT_BYTES, parse_yaml

STORE_ENV = "LOOPSPEC_REGISTRY_STORE"
LOCK_FILE = "registry.lock.yaml"
SNAPSHOT_FILE = ".snapshot.json"
HASH_RE = r"^[0-9a-f]{64}$"
COMMIT_PATTERN = r"^([0-9a-f]{40}|[0-9a-f]{64})$"
_NAME = r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*"
_SEGMENT = r"[A-Za-z0-9._-]+"
FILE_RE = re.compile(rf"^(fragments/{_NAME}(?:/{_SEGMENT})+|profiles/{_NAME}\.yaml)$")
DEFINITION_RE = re.compile(rf"^(fragments|profiles)/({_NAME})$")
T = TypeVar("T")
SYNC_FIX = "运行 loopspec registry update，确认后 loopspec registry apply --plan <planId>。"


# --------------------------------------------------------------------- paths


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


def owning_key(path: str) -> str | None:
    """The definition a home-relative path belongs to, if it is inside one."""
    parts = path.split("/")
    if parts[0] == "fragments" and len(parts) >= 3:
        return f"fragments/{parts[1]}"
    if parts[0] == "profiles" and len(parts) == 2 and parts[1].endswith(".yaml"):
        return f"profiles/{parts[1][:-5]}"
    return None


def _check_files(files: dict[str, str], limit: int = MAX_FILES) -> dict[str, str]:
    if len(files) > limit:
        raise ValueError("文件表条目超过限额")
    for path, value in files.items():
        if not is_definition_file(path) or not re.fullmatch(HASH_RE, value):
            raise ValueError("files 条目不合法")
    return files


# ---------------------------------------------------------------------- lock


class RegistryLockV1(StrictModel):
    """Legacy lock: definitions vendored into the project, per-definition versions."""

    version: Literal[1] = 1
    registry: RegistrySpec
    commit: str = Field(pattern=COMMIT_PATTERN)
    tag: str | None = None
    definitions: dict[str, dict] = Field(default_factory=dict, max_length=4096)
    held: list[str] = Field(default_factory=list, max_length=4096)
    files: dict[str, str] = Field(default_factory=dict, max_length=8192)

    @field_validator("tag")
    @classmethod
    def valid_tag(cls, value: str | None) -> str | None:
        return None if value is None else check_tag(value)

    @model_validator(mode="after")
    def valid_keys(self) -> RegistryLockV1:
        for key in [*self.definitions, *self.held]:
            if not DEFINITION_RE.fullmatch(key):
                raise ValueError("definitions / held 键不合法")
        # The old format could keep skipped files the registry already deleted.
        _check_files(self.files, limit=8192)
        return self


class RegistryLock(StrictModel):
    """`<home>/registry.lock.yaml` v2: the one registry commit the project uses."""

    version: Literal[2] = 2
    registry: RegistrySpec
    commit: str = Field(pattern=COMMIT_PATTERN)
    tag: str | None = None
    files: dict[str, str] = Field(default_factory=dict, max_length=MAX_FILES)

    @field_validator("tag")
    @classmethod
    def valid_tag(cls, value: str | None) -> str | None:
        return None if value is None else check_tag(value)

    @field_validator("files")
    @classmethod
    def valid_files(cls, value: dict[str, str]) -> dict[str, str]:
        return _check_files(value)


@dataclass(frozen=True)
class LockFile:
    """A lock as found on disk: the parsed model plus the hash of its exact bytes."""

    lock: RegistryLock | RegistryLockV1
    raw_hash: str

    @property
    def is_v2(self) -> bool:
        return isinstance(self.lock, RegistryLock)


def read_lock(home: Path) -> LockFile | None:
    """The project lock in either format; `None` when there is none."""
    if not os.path.lexists(home / LOCK_FILE):
        return None
    try:
        raw = read_bytes(home, LOCK_FILE)
    except WorkflowError as exc:
        if exc.code != "resource_limit":
            raise
        raise WorkflowError(
            "config_invalid",
            "registry.lock.yaml 结构不合法",
            "从版本库恢复 registry.lock.yaml，或删除它后重新同步。",
        ) from exc
    try:
        value = parse_yaml(raw)
        model: type[RegistryLock] | type[RegistryLockV1] = (
            RegistryLockV1 if value.get("version") == 1 else RegistryLock
        )
        lock = model.model_validate(value)
    except (ValueError, ValidationError) as exc:
        raise WorkflowError(
            "config_invalid",
            "registry.lock.yaml 结构不合法",
            "从版本库恢复 registry.lock.yaml，或删除它后重新同步。",
        ) from exc
    return LockFile(lock, byte_hash(raw))


def lock_bytes(lock: RegistryLock) -> bytes:
    text = yaml.safe_dump(
        lock.model_dump(), allow_unicode=True, sort_keys=False, width=1000
    ).encode("utf-8")
    if len(text) > MAX_DOCUMENT_BYTES:
        raise WorkflowError("resource_limit", "registry.lock.yaml 超过大小限额")
    return text


def same_source(spec: RegistrySpec, other: RegistrySpec) -> bool:
    return spec.url == other.url and spec.path == other.path


@dataclass(frozen=True)
class Pin:
    """What a project uses: one registry commit and the hash of every file in it."""

    spec: RegistrySpec
    commit: str
    tag: str | None
    files: dict[str, str]
    raw_hash: str

    @property
    def keys(self) -> set[str]:
        return {definition_key(path) for path in self.files}


def pinned(home: Path, spec: RegistrySpec) -> Pin:
    """The lock as a usable pin, or the reason the project must sync first."""
    found = read_lock(home)
    if found is None:
        raise WorkflowError(
            "registry_not_synced", "registry 模式的项目缺少 registry.lock.yaml", SYNC_FIX
        )
    lock = found.lock
    if not same_source(spec, lock.registry):
        raise WorkflowError(
            "registry_lock_mismatch",
            "registry.lock.yaml 的来源（url/path）与 config.yaml 不一致",
            SYNC_FIX,
        )
    if spec.version != "latest" and lock.tag != spec.version:
        # A pinned project must run the pinned tag: a lock without it (or with another)
        # would skip the tag-to-commit check that keeps unreleased commits out.
        raise WorkflowError(
            "registry_lock_mismatch",
            "registry.lock.yaml 的 tag 与 config.yaml 固定的 registry.version 不一致",
            SYNC_FIX,
        )
    if isinstance(lock, RegistryLockV1) and (
        lock.held or any(value.get("commit") != lock.commit for value in lock.definitions.values())
    ):
        raise WorkflowError(
            "registry_lock_outdated",
            "旧格式 registry.lock.yaml 含有未同步的定义，无法对应单一 registry 版本",
            SYNC_FIX,
        )
    return Pin(spec, lock.commit, lock.tag, dict(lock.files), found.raw_hash)


# --------------------------------------------------------------------- store


def store_root() -> Path:
    value = os.environ.get(STORE_ENV)
    root = Path(value).expanduser() if value else Path.home() / ".loopspec" / "registry"
    return Path(os.path.abspath(root))


_SLUG_LIMIT = 48


def source_id(spec: RegistrySpec) -> str:
    """`<repository>[-<path>]-<hash8>`: readable in a directory listing, unique by the hash.

    The readable part is the last segment of the URL (without `.git`) plus `path`,
    lower-cased and reduced to `[a-z0-9-]`; the hash covers the exact `url` and `path`,
    so two spellings of one repository (ssh and https) stay separate sources.
    """
    digest = hashlib.sha256(f"{spec.url}\n{spec.path or ''}".encode()).hexdigest()[:8]
    name = re.split(r"[/:]", spec.url.rstrip("/"))[-1]
    name = name[:-4] if name.endswith(".git") else name
    readable = "-".join(part for part in (name, spec.path or "") if part)
    slug = re.sub(r"[^a-z0-9]+", "-", readable.lower()).strip("-")[:_SLUG_LIMIT].strip("-")
    return f"{slug or 'registry'}-{digest}"


def _unsafe_store() -> WorkflowError:
    return WorkflowError(
        "unsafe_path",
        "registry 全局存储目录不是当前用户私有的普通目录",
        f"检查 {STORE_ENV}（默认 ~/.loopspec/registry）：必须属于当前用户、"
        "路径中没有符号链接，且组和其他用户不可写。",
    )


def _private_dir(path: Path) -> None:
    """Create `path` (0700) if needed; it must be ours, a real dir, not group/world writable.

    Creation starts from the deepest existing ancestor and every component is opened with
    O_NOFOLLOW before anything is created under it, so a symlink anywhere in the path is
    refused without having created directories behind it.
    """
    base = path
    while not os.path.lexists(base) and base.parent != base:
        base = base.parent
    relative = "" if base == path else path.relative_to(base).as_posix()
    try:
        with directory(base, relative, create=True):
            pass
    except WorkflowError as exc:
        raise _unsafe_store() from exc
    info = os.lstat(path)
    if (
        stat.S_ISLNK(info.st_mode)
        or not stat.S_ISDIR(info.st_mode)
        or info.st_uid != os.getuid()
        or info.st_mode & 0o022
    ):
        raise _unsafe_store()


class SnapshotManifest(StrictModel):
    version: Literal[1] = 1
    url: str
    path: str | None = None
    commit: str = Field(pattern=COMMIT_PATTERN)
    #: Tags verified to point at `commit` when the snapshot was published.
    tags: list[str] = Field(default_factory=list, max_length=16)
    files: dict[str, str]

    @field_validator("files")
    @classmethod
    def valid_files(cls, value: dict[str, str]) -> dict[str, str]:
        return _check_files(value)

    @field_validator("tags")
    @classmethod
    def valid_tags(cls, value: list[str]) -> list[str]:
        return [check_tag(tag) for tag in value]


_VERIFIED: set[tuple[str, str]] = set()
_VERIFIED_TAGS: dict[str, list[str]] = {}
#: (url, path, tag, commit) bindings checked online in this process.
_TAG_BINDINGS: set[tuple[str, str, str, str]] = set()


def _corrupt(target: Path) -> WorkflowError:
    return WorkflowError(
        "registry_store_corrupt",
        f"registry 全局存储中的快照与 registry.lock.yaml 不一致：{target}",
        "删除该快照目录后重试，下次读取会按 lock 重新拉取。",
    )


def _verify(target: Path, spec: RegistrySpec, commit: str, files: dict[str, str]) -> list[str]:
    """Check the snapshot completely against `files`; returns the tags verified at publish."""
    key = (str(target), hashlib.sha256(canonical(files)).hexdigest())
    if key in _VERIFIED:
        return _VERIFIED_TAGS.get(str(target), [])
    try:
        info = os.lstat(target)
        if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
            raise _corrupt(target)
        manifest = SnapshotManifest.model_validate_json(read_bytes(target, SNAPSHOT_FILE))
        if (
            manifest.url != spec.url
            or manifest.path != spec.path
            or manifest.commit != commit
            or manifest.files != files
        ):
            raise _corrupt(target)
        for path, value in files.items():
            if byte_hash(read_bytes(target, path)) != value:
                raise _corrupt(target)
    except (OSError, ValueError, ValidationError) as exc:
        raise _corrupt(target) from exc
    except WorkflowError as exc:
        if exc.code == "registry_store_corrupt":
            raise
        raise _corrupt(target) from exc
    _VERIFIED.add(key)
    _VERIFIED_TAGS[str(target)] = list(manifest.tags)
    return list(manifest.tags)


def _object_format(commit: str) -> str:
    return "sha256" if len(commit) == 64 else "sha1"


def _workdir(spec: RegistrySpec) -> tuple[Path, Path]:
    """A fresh private scratch directory under the source directory."""
    root = store_root()
    _private_dir(root)
    source = root / source_id(spec)
    _private_dir(source)
    scratch = source / (".tmp-" + uuid.uuid4().hex)
    os.mkdir(scratch, 0o700)
    return source, scratch


def materialize(
    spec: RegistrySpec,
    commit: str,
    tag: str | None,
    files: dict[str, str],
    content: dict[str, bytes] | None = None,
) -> Path:
    """The verified snapshot of `commit`, fetching and publishing it when missing.

    `files` is the trusted file table (from the lock or an apply plan, or derived
    from the git tree by the caller); `content`, when given, is that tree's bytes.
    """
    if not re.fullmatch(COMMIT_PATTERN, commit):
        raise WorkflowError("registry_invalid", "commit 不合法")
    root = store_root()
    _private_dir(root)
    source = root / source_id(spec)
    _private_dir(source)
    target = source / commit
    if os.path.lexists(target):
        verified = _verify(target, spec, commit, files)
        if tag is not None and tag not in verified:
            _check_tag_online(spec, tag, commit)
        return target
    source, scratch = _workdir(spec)
    try:
        if content is None:
            repo = RegistryRepo(scratch / "work", spec, object_format=_object_format(commit))
            repo.fetch_commit(commit, tag)
            content = repo.read_tree(commit).files
        if {path: byte_hash(data) for path, data in content.items()} != files:
            raise WorkflowError(
                "registry_lock_mismatch",
                "registry 中该版本的内容与 registry.lock.yaml 记录的文件不一致",
                "确认 registry.lock.yaml 未被误改，或重新 loopspec registry update。",
            )
        snapshot = scratch / "snapshot"
        os.mkdir(snapshot, 0o700)
        for path, data in sorted(content.items()):
            atomic_write(snapshot, path, data)
        # `tag` was checked by fetch_commit, or resolved by ls-remote for update's content.
        manifest = SnapshotManifest(
            url=spec.url, path=spec.path, commit=commit, tags=[tag] if tag else [], files=files
        )
        atomic_write(snapshot, SNAPSHOT_FILE, canonical(manifest.model_dump()) + b"\n")
        try:
            os.rename(snapshot, target)
        except OSError:
            # Another process published the same commit first; verify theirs below.
            if not os.path.lexists(target):
                raise
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
    verified = _verify(target, spec, commit, files)
    if tag is not None and tag not in verified:
        # Another process published this commit first without recording our tag.
        _check_tag_online(spec, tag, commit)
    return target


def _check_tag_online(spec: RegistrySpec, tag: str, commit: str) -> None:
    """A lock's tag must point at its commit before a cached snapshot is used under it."""
    key = (spec.url, spec.path or "", tag, commit)
    if key in _TAG_BINDINGS:
        return
    source = store_root() / source_id(spec)
    record = f"tags/{check_tag(tag)}"
    # The record names its source too: source ids carry a short hash, so a colliding
    # source must never borrow another source's verified binding.
    binding = canonical({"url": spec.url, "path": spec.path, "tag": tag, "commit": commit})
    try:
        if read_bytes(source, record).strip() == binding:
            _TAG_BINDINGS.add(key)
            return
    except WorkflowError:
        pass
    read_remote(spec, lambda repo: repo.verify_tag(commit, tag))
    # Kept in the private store so later processes (and offline use) trust this binding.
    atomic_write(source, record, binding + b"\n")
    _TAG_BINDINGS.add(key)


def read_remote(spec: RegistrySpec, operate: Callable[[RegistryRepo], T]) -> T:
    """Run `operate(repo)` against a fresh scratch repository, cleaned up afterwards."""
    _, scratch = _workdir(spec)
    try:
        return operate(RegistryRepo(scratch / "work", spec))
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


# ------------------------------------------------------------------- bundle


class DefinitionBundle(ResourceBundle):
    """Reads registry definitions from the verified snapshot and everything else from home."""

    def __init__(self, home: Path, snapshot: Path, pin: Pin) -> None:
        super().__init__(home)
        self.snapshot = snapshot
        self.pin = pin
        self.registry_keys = pin.keys

    def is_registry(self, path: str) -> bool:
        key = owning_key(path)
        return key is not None and key in self.registry_keys

    def location(self, path: str) -> Path:
        """Registry definitions live in the verified snapshot, everything else in home."""
        path = relative_path(path)
        if self.is_registry(path):
            return self.snapshot.resolve() / path
        return super().location(path)

    def read(self, path: str) -> bytes:
        path = relative_path(path)
        if path in self.files:
            return self.files[path]
        if self.is_registry(path):
            expected = self.pin.files.get(path)
            if expected is None:
                raise WorkflowError("unsafe_path", "registry 定义中不存在该资源文件")
            value = read_bytes(self.snapshot, path)
            if byte_hash(value) != expected:
                raise _corrupt(self.snapshot)
        else:
            value = read_bytes(self.root, path)
        self.total += len(value)
        if self.total > MAX_BUNDLE_BYTES or len(self.files) >= 2048:
            raise WorkflowError("resource_limit", "编译资源超过累计限额")
        self.files[path] = value
        return value


def registry_spec(home: Path) -> RegistrySpec | None:
    """The configured registry, `None` for projects that vendor their own definitions."""
    if not exists(home, "config.yaml"):
        return None
    # Only a config that declares `registry` is validated here: commands that never read
    # config.yaml before must keep working for projects without a registry.
    raw = read_bytes(home, "config.yaml")
    try:
        declared = "registry" in parse_yaml(raw)
    except ValueError:
        # Unparseable: only a config that could declare a registry goes to the strict
        # loader (which reports the real problem); others behave as before.
        declared = b"registry" in raw
    if not declared:
        return None
    from .workflow_planning import load_config

    return load_config(home).registry


def local_conflicts(home: Path, keys: set[str]) -> list[str]:
    """Project paths that would shadow a registry definition of the same name."""
    found = []
    for key in sorted(keys):
        kind, name = key.split("/")
        path = f"fragments/{name}" if kind == "fragments" else f"profiles/{name}.yaml"
        if os.path.lexists(home / path):
            found.append(path)
    return found


def conflict_error(paths: list[str]) -> WorkflowError:
    return WorkflowError(
        "registry_local_conflict",
        "项目内存在与 registry 同名的定义：" + "、".join(paths),
        "registry 模式下这些定义由 registry.lock.yaml 提供；删除项目内的这些副本后重试。",
    )


def bundle_for(home: Path, pin: Pin, *, snapshot: Path | None = None) -> DefinitionBundle:
    conflicts = local_conflicts(home, pin.keys)
    if conflicts:
        raise conflict_error(conflicts)
    if snapshot is None:
        snapshot = materialize(pin.spec, pin.commit, pin.tag, pin.files)
    return DefinitionBundle(home, snapshot, pin)


_SNAPSHOTS: dict[tuple[str, str], Path] = {}


def definition_bundle(home: Path) -> ResourceBundle:
    """The bundle every definition read goes through (catalog, runtime, assurance)."""
    spec = registry_spec(home)
    if spec is None:
        return ResourceBundle(home)
    pin = pinned(home, spec)
    key = (os.path.abspath(home), pin.raw_hash)
    snapshot = _SNAPSHOTS.get(key)
    bundle = bundle_for(home, pin, snapshot=snapshot)
    _SNAPSHOTS[key] = bundle.snapshot
    return bundle
