"""固定基线下的有界代码输入快照；只返回路径、类型/模式与摘要，不返回代码。"""

from __future__ import annotations

import fnmatch
import hashlib
import os
import re
import stat
from dataclasses import dataclass, field
from pathlib import Path

from .errors import WorkflowError
from .workflow_git import fixed_baseline, git
from .workflow_io import (
    MAX_BUNDLE_BYTES,
    MAX_FILE_BYTES,
    byte_hash,
    digest,
    directory,
    read_bytes,
    relative_path,
)
from .workflow_state import LoadedPlan


def _delivered(entries: list[dict]) -> list[dict]:
    # Digests bind what is delivered, not what is staged: git add or commit must not stale
    # evidence. Partial staging is still rejected while scanning (index vs HEAD and worktree).
    return [{key: value for key, value in entry.items() if key != "index"} for entry in entries]


# Ignored paths only warn; the list is capped so reports and outputs stay small.
MAX_IGNORED_WARNINGS = 20


@dataclass
class DiffSnapshot:
    baseline: str
    entries: list[dict]
    # Ignored, not excluded paths: never part of any digest, reported as warnings only.
    ignored: list[str] = field(default_factory=list)
    # Paths whose content in HEAD is neither the baseline nor the delivered worktree: what
    # git would ship there was never reviewed. Never part of any digest; assurance fails on it.
    diverged: list[str] = field(default_factory=list)

    def warnings(self) -> dict | None:
        if not self.ignored:
            return None
        return {
            "ignoredPaths": self.ignored[:MAX_IGNORED_WARNINGS],
            "ignoredTotal": len(self.ignored),
        }

    @property
    def diff_digest(self) -> str:
        return digest({"baseline": self.baseline, "entries": _delivered(self.entries)})

    def scope(self, patterns: list[str]) -> list[dict]:
        return [
            entry
            for entry in self.entries
            if any(fnmatch.fnmatchcase(entry["path"], pattern) for pattern in patterns)
        ]

    def scope_digest(self, patterns: list[str]) -> str:
        return digest(
            {
                "baseline": self.baseline,
                "patterns": patterns,
                "entries": _delivered(self.scope(patterns)),
            }
        )


def _decode_path(value: bytes) -> str:
    try:
        result = value.decode("utf-8", errors="strict")
        relative_path(result)
        return result
    except (UnicodeError, WorkflowError) as exc:
        raise WorkflowError("unsupported_input", "Git 路径编码或目录分量不支持") from exc


def _records(data: bytes) -> list[bytes]:
    if data and not data.endswith(b"\0"):
        raise WorkflowError("git_input_error", "Git NUL 清单不完整")
    records = data.split(b"\0")[:-1]
    if len(records) > 4096:
        raise WorkflowError("resource_limit", "Git 输入文件超过数量限制")
    return records


def _objects(data: bytes, *, index: bool) -> dict[str, tuple[str, str]]:
    result = {}
    for record in _records(data):
        try:
            fields, path = record.split(b"\t", 1)
            mode, middle, last = fields.decode("ascii").split(" ")
            oid = middle if index else last
            if index and last != "0":
                raise WorkflowError("unsupported_input", "存在未解决的 Index 合并冲突")
            if not index and middle != "blob":
                raise WorkflowError("unsupported_input", "不支持子模块内部改动")
            if mode not in {"100644", "100755", "120000"} or not re.fullmatch(
                r"[0-9a-f]{40}|[0-9a-f]{64}", oid
            ):
                raise WorkflowError("unsupported_input", "不支持 Git 对象类型或文件模式")
            name = _decode_path(path)
            if name in result:
                raise WorkflowError("git_input_error", "Git 清单存在重复路径")
            result[name] = (mode, oid)
        except (ValueError, UnicodeError) as exc:
            raise WorkflowError("git_input_error", "Git 对象清单结构不合法") from exc
    return result


def _exclusions(loaded: LoadedPlan, repository: Path):
    from .workflow_planning import project_constraints

    patterns = project_constraints(loaded.home).excluded_paths
    names = [pattern for pattern in patterns if "/" not in pattern]
    paths = [pattern for pattern in patterns if "/" in pattern]
    try:
        change = loaded.change.root.absolute().relative_to(repository).as_posix()
    except ValueError as exc:
        raise WorkflowError("repository_changed", "需求目录不属于固定仓库") from exc
    relative_path(change)
    try:
        home = loaded.home.absolute().relative_to(repository).as_posix()
    except ValueError:
        home = None
    # The registry sync cache lives under <home>/.cache and is never delivery input.
    cache = ".cache" if home == "." else f"{home}/.cache"

    def excluded(path: str, *, directory: bool = False) -> bool:
        # This Change's own control paths and the workflow cache are always out of the Diff.
        if path in {change + "/.workflow.yaml", change + "/state.md"}:
            return True
        if path == change + "/plans" or path.startswith(change + "/plans/"):
            return True
        if home is not None and (path == cache or path.startswith(cache + "/")):
            return True
        if any(fnmatch.fnmatchcase(part, name) for part in path.split("/") for name in names):
            return True
        target = path + "/" if directory else path
        return any(fnmatch.fnmatchcase(target, pattern) for pattern in paths)

    return excluded


def collect_diff(loaded: LoadedPlan) -> DiffSnapshot:
    state = loaded.change.state
    if not state.baseline or not state.repository:
        raise WorkflowError("baseline_required", "代码证据要求固定 Git 基线")
    baseline, actual_repository = fixed_baseline(loaded.change.root, state.baseline)
    if actual_repository != state.repository:
        raise WorkflowError("repository_changed", "Git 仓库身份发生变化")
    repository = Path(actual_repository)
    excluded = _exclusions(loaded, repository)
    base_raw = git(repository, ["ls-tree", "-rz", "--full-tree", baseline])
    base = _objects(base_raw, index=False)
    blobs: dict[str, tuple[str, int]] = {}
    total = 0
    oids: dict[str, str] = {}

    def object_id(data: bytes, width: int) -> str:
        # Git's own blob id, so unchanged paths are recognised without reading any blob.
        header = b"blob %d\0" % len(data)
        digest_type = hashlib.sha1 if width == 40 else hashlib.sha256
        return digest_type(header + data).hexdigest()

    def blob(mode_oid: tuple[str, str] | None):
        nonlocal total
        if mode_oid is None:
            return None
        mode, oid = mode_oid
        if oid not in blobs:
            size_raw = git(repository, ["cat-file", "-s", oid], limit=64)
            try:
                size = int(size_raw)
            except ValueError as exc:
                raise WorkflowError("git_input_error", "Git 对象长度不合法") from exc
            if size < 0 or size > MAX_FILE_BYTES:
                raise WorkflowError("resource_limit", "代码文件超过大小限制")
            total += size
            if total > MAX_BUNDLE_BYTES:
                raise WorkflowError("resource_limit", "代码输入超过累计限制")
            data = git(repository, ["cat-file", "blob", oid], limit=MAX_FILE_BYTES)
            if len(data) != size:
                raise WorkflowError("concurrent_input_change", "Git 对象长度变化")
            blobs[oid] = (byte_hash(data), size)
        content_hash, size = blobs[oid]
        return {"mode": mode, "sha256": content_hash, "size": size}

    def worktree(path: str, reference: tuple[str, str] | None = None):
        nonlocal total
        parts = path.split("/")
        try:
            with directory(repository, "/".join(parts[:-1])) as fd:
                info = os.stat(parts[-1], dir_fd=fd, follow_symlinks=False)
                if stat.S_ISLNK(info.st_mode):
                    target = os.readlink(parts[-1], dir_fd=fd).encode("utf-8", errors="strict")
                    after = os.stat(parts[-1], dir_fd=fd, follow_symlinks=False)
                    if (info.st_ino, info.st_mtime_ns, info.st_ctime_ns) != (
                        after.st_ino,
                        after.st_mtime_ns,
                        after.st_ctime_ns,
                    ):
                        raise WorkflowError("concurrent_input_change", "符号链接在读取期间变化")
                    mode, data = "120000", target
                elif stat.S_ISREG(info.st_mode):
                    mode = "100755" if info.st_mode & 0o111 else "100644"
                    data = read_bytes(repository, path)
                    after = os.stat(parts[-1], dir_fd=fd, follow_symlinks=False)
                    if (info.st_ino, info.st_mode) != (after.st_ino, after.st_mode):
                        raise WorkflowError(
                            "concurrent_input_change", "文件模式或身份在读取期间变化"
                        )
                else:
                    raise WorkflowError("unsupported_input", "代码路径不是普通文件或符号链接")
        except WorkflowError as exc:
            if isinstance(exc.__cause__, FileNotFoundError):
                return None
            raise
        except UnicodeError as exc:
            raise WorkflowError("unsupported_input", "符号链接文本不可解码") from exc
        total += len(data)
        if total > MAX_BUNDLE_BYTES:
            raise WorkflowError("resource_limit", "代码输入超过累计限制")
        if reference:
            oids[path] = mode + " " + object_id(data, len(reference[1]))
        return {"mode": mode, "sha256": byte_hash(data), "size": len(data)}

    def scan():
        nonlocal total
        total = sum(size for _, size in blobs.values())
        head = git(repository, ["rev-parse", "--verify", "HEAD"])
        index_raw = git(repository, ["ls-files", "--stage", "-z"])
        index = _objects(index_raw, index=True)
        committed = _objects(
            git(repository, ["ls-tree", "-rz", "--full-tree", "HEAD"]), index=False
        )
        others_raw = git(repository, ["ls-files", "--others", "--exclude-standard", "-z"])
        others = {_decode_path(item) for item in _records(others_raw)}
        ignored_raw = git(
            repository,
            ["ls-files", "--others", "--ignored", "--exclude-standard", "--directory", "-z"],
        )
        listed = [
            (_decode_path(item.removesuffix(b"/")), item.endswith(b"/"))
            for item in _records(ignored_raw)
        ]
        # Git also lists a directory that merely holds ignored entries, followed by those
        # entries; only the entries themselves are judged.
        containers = {
            "/".join(parts[:end])
            for parts in (path.split("/") for path, _ in listed)
            for end in range(1, len(parts))
        }
        ignored = []
        for path, is_directory in listed:
            if is_directory and path in containers:
                continue
            if not excluded(path, directory=is_directory):
                ignored.append(path + "/" if is_directory else path)
        paths = sorted(set(base) | set(index) | set(committed) | others)
        if len(paths) > 4096:
            raise WorkflowError("resource_limit", "输入文件超过数量限制")
        entries = []
        diverged = []
        for path in paths:
            if excluded(path):
                continue
            known = base.get(path)
            current = worktree(path, known or index.get(path))
            if (
                current is not None
                and known is not None
                and known == index.get(path)
                and known == committed.get(path)
                and oids.get(path) == " ".join(known)
            ):
                continue
            original, staged = blob(base.get(path)), blob(index.get(path))
            if committed.get(path) != known:
                shipped = blob(committed.get(path))
                if shipped != original and shipped != current:
                    diverged.append(path)
            # A staged version that is neither committed nor in the worktree leaves the
            # delivery ambiguous. Commits after the baseline are normal, so compare with HEAD.
            if staged != current and staged != blob(committed.get(path)):
                raise WorkflowError(
                    "index_worktree_mismatch", "已暂存输入与工作树不一致，必须先明确交付版本"
                )
            if original != current:
                kind = "added" if original is None else "deleted" if current is None else "modified"
                entries.append(
                    {
                        "path": path,
                        "kind": kind,
                        "base": original,
                        "index": staged,
                        "worktree": current,
                    }
                )
        if index_raw != git(repository, ["ls-files", "--stage", "-z"]) or head != git(
            repository, ["rev-parse", "--verify", "HEAD"]
        ):
            raise WorkflowError("concurrent_input_change", "扫描期间 HEAD 或 Index 发生变化")
        removed = [entry for entry in entries if entry["kind"] == "deleted"]
        added = [entry for entry in entries if entry["kind"] == "added"]
        for entry in added:
            matches = [prior for prior in removed if prior["base"] == entry["worktree"]]
            if len(matches) == 1:
                prior = matches[0]
                entry["renamed_from"] = prior["path"]
                prior["renamed_to"] = entry["path"]
                removed.remove(prior)
        return entries, index_raw, others_raw, sorted(ignored), head, diverged

    first = scan()
    second = scan()
    if first != second:
        raise WorkflowError("concurrent_input_change", "连续扫描结果不一致")
    return DiffSnapshot(baseline, second[0], second[3], second[5])
