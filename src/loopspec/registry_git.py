"""Registry 远程边界：受限的 git 子进程、ls-remote 预检、浅拉取与只读对象树读取。

所有来自配置、远端 ref 列表与远端树的值都视为不可信：URL 已由 `RegistrySpec`
校验，ref/commit/路径在这里逐项校验后才进入参数或结果。仓库是私有裸仓库，
从不 checkout，因此远端的 hook、过滤器与符号链接不会在本地生效或落盘。
"""

from __future__ import annotations

import os
import re
import selectors
import shutil
import stat
import subprocess
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

from .errors import WorkflowError
from .models import KEBAB_RE, RegistrySpec, check_tag, registry_scheme
from .workflow_io import MAX_BUNDLE_BYTES, MAX_FILE_BYTES, directory, relative_path

COMMIT_RE = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")
# Path segments that are safe to hand to an agent and through it to a shell:
# no whitespace, quotes, `$`, backticks, `;` or bidirectional controls.
SEGMENT_RE = re.compile(r"^[A-Za-z0-9._-]+$")
RELEASE_RE = re.compile(r"^v?(\d+)(?:\.(\d+))?(?:\.(\d+))?$")
MAX_FILES = 2048
MAX_DEPTH = 8
OUTPUT_LIMIT = 32 * 1024 * 1024
UPSTREAM_REF = "refs/loopspec/upstream"
BASE_REF = "refs/loopspec/base"
FETCH_FIX = "检查 registry.url、网络与本机 git 凭据（SSH agent 或 credential helper）后重试。"

# Variables that would point git at another repository, inject configuration or
# change which protocols are allowed. Everything else (SSH agent, credential
# helpers, proxies) is inherited so private registries keep working.
_DROPPED_ENV = {
    "GIT_DIR",
    "GIT_WORK_TREE",
    "GIT_INDEX_FILE",
    "GIT_OBJECT_DIRECTORY",
    "GIT_ALTERNATE_OBJECT_DIRECTORIES",
    "GIT_COMMON_DIR",
    "GIT_NAMESPACE",
    "GIT_CEILING_DIRECTORIES",
    "GIT_DISCOVERY_ACROSS_FILESYSTEM",
    "GIT_CONFIG",
    "GIT_CONFIG_PARAMETERS",
    "GIT_CONFIG_COUNT",
    "GIT_CONFIG_NOSYSTEM",
    "GIT_EXEC_PATH",
    "GIT_TEMPLATE_DIR",
    "GIT_ALLOW_PROTOCOL",
    "GIT_PROTOCOL_FROM_USER",
    "GIT_SHALLOW_FILE",
    "GIT_REPLACE_REF_BASE",
    "GIT_NO_REPLACE_OBJECTS",
}
_CREDENTIAL_RE = re.compile(r"([A-Za-z][A-Za-z0-9+.-]*://)[^/@\s]+@")


def redact(stderr: bytes) -> str:
    """The last 20 lines of git stderr, credentials masked, at most 2000 characters."""
    text = stderr.decode("utf-8", "replace")
    text = "".join(c if c in "\n\t" or 32 <= ord(c) != 127 else "?" for c in text)
    text = _CREDENTIAL_RE.sub(r"\1***@", text)
    lines = text.strip().splitlines()[-20:]
    return "\n".join(lines)[-2000:]


def _feed(process: subprocess.Popen[bytes], data: bytes) -> None:
    assert process.stdin
    try:
        process.stdin.write(data)
    except (BrokenPipeError, ValueError, OSError):
        pass
    finally:
        try:
            process.stdin.close()
        except OSError:
            pass


def _environment() -> dict[str, str]:
    environment = {
        key: value
        for key, value in os.environ.items()
        if key not in _DROPPED_ENV
        and not key.startswith(("GIT_CONFIG_KEY_", "GIT_CONFIG_VALUE_", "GIT_TRACE"))
    }
    environment.update({"GIT_TERMINAL_PROMPT": "0", "LC_ALL": "C"})
    return environment


def run_git(
    arguments: list[str],
    *,
    scheme: str,
    git_dir: Path | None = None,
    timeout: float = 30,
    stdin: bytes | None = None,
    limit: int = OUTPUT_LIMIT,
    code: str = "registry_fetch_failed",
) -> bytes:
    command = [
        "git",
        "-c",
        "protocol.allow=never",
        "-c",
        f"protocol.{scheme}.allow=always",
        "-c",
        "core.hooksPath=" + os.devnull,
        "-c",
        "init.templateDir=",
        "-c",
        "transfer.fsckObjects=true",
        "-c",
        "submodule.recurse=false",
        "-c",
        "core.fsmonitor=false",
        "-c",
        "http.followRedirects=false",
    ]
    if git_dir is not None:
        command.append("--git-dir=" + str(git_dir))
    command.extend(arguments)
    try:
        process = subprocess.Popen(
            command,
            env=_environment(),
            cwd=git_dir if git_dir is not None and git_dir.is_dir() else None,
            stdin=subprocess.PIPE if stdin is not None else subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except FileNotFoundError as exc:
        raise WorkflowError(
            "registry_unavailable", "未找到 git 可执行文件", "安装 git 并确认它在 PATH 中。"
        ) from exc
    stdout, stderr = bytearray(), bytearray()
    writer = None
    if stdin is not None:
        # Written concurrently with the reads below: git streams output while it
        # consumes the request, so a blocking write could deadlock outside the timeout.
        writer = threading.Thread(target=_feed, args=(process, stdin), daemon=True)
        writer.start()
    try:
        assert process.stdout and process.stderr
        deadline = time.monotonic() + timeout
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ, stdout)
            selector.register(process.stderr, selectors.EVENT_READ, stderr)
            while selector.get_map():
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise subprocess.TimeoutExpired("git", timeout)
                for key, _ in selector.select(min(remaining, 0.25)):
                    piece = os.read(key.fd, 65536)
                    if not piece:
                        selector.unregister(key.fileobj)
                        continue
                    buffer: bytearray = key.data
                    buffer.extend(piece)
                    if buffer is stdout and len(stdout) > limit:
                        raise WorkflowError("registry_invalid", "registry 输出超过限额")
                    if buffer is stderr and len(stderr) > 65536:
                        del stderr[: len(stderr) - 65536]
        returncode = process.wait(timeout=max(deadline - time.monotonic(), 0.1))
    except subprocess.TimeoutExpired as exc:
        process.kill()
        process.wait()
        raise WorkflowError(code, "git 操作超时", FETCH_FIX) from exc
    except BaseException:
        process.kill()
        process.wait()
        raise
    if returncode != 0:
        detail = redact(bytes(stderr))
        raise WorkflowError(
            code, f"git 退出码 {returncode}" + (f"：{detail}" if detail else ""), FETCH_FIX
        )
    return bytes(stdout)


@dataclass(frozen=True)
class Target:
    """The upstream commit an update syncs to and how it was named."""

    commit: str
    tag: str | None
    ref: str


@dataclass
class RemoteTree:
    files: dict[str, bytes] = field(default_factory=dict)
    unsupported: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def parse_ls_remote(data: bytes) -> tuple[str | None, dict[str, str]]:
    """`HEAD` and tag → commit from ls-remote output; malformed lines are dropped."""
    head: str | None = None
    direct: dict[str, str] = {}
    peeled: dict[str, str] = {}
    for raw in data.split(b"\n"):
        try:
            line = raw.decode("ascii")
        except UnicodeDecodeError:
            continue
        commit, sep, ref = line.partition("\t")
        if not sep or not COMMIT_RE.fullmatch(commit):
            continue
        if ref == "HEAD":
            head = commit
            continue
        if not ref.startswith("refs/tags/"):
            continue
        name = ref[len("refs/tags/") :]
        target = direct
        if name.endswith("^{}"):
            name, target = name[:-3], peeled
        try:
            check_tag(name)
        except ValueError:
            continue
        target[name] = commit
    return head, {name: peeled.get(name, commit) for name, commit in direct.items()}


def select_latest(head: str | None, tags: dict[str, str]) -> Target:
    releases = []
    for name, commit in tags.items():
        match = RELEASE_RE.fullmatch(name)
        if match:
            releases.append((tuple(int(part or 0) for part in match.groups()), name, commit))
    if releases:
        _, name, commit = max(releases)
        return Target(commit=commit, tag=name, ref="refs/tags/" + name)
    if head is None:
        raise WorkflowError(
            "registry_fetch_failed", "registry 没有 release tag 也没有 HEAD", FETCH_FIX
        )
    return Target(commit=head, tag=None, ref="HEAD")


class RegistryRepo:
    """A private bare repository under `<cache>/repo.git` mirroring one registry."""

    def __init__(self, cache: Path, spec: RegistrySpec) -> None:
        self.cache = cache
        self.spec = spec
        self.scheme = registry_scheme(spec.url)
        # Absolute: git runs with this directory as its cwd, so a relative
        # `--git-dir` would resolve against itself.
        self.git_dir = (cache / "repo.git").absolute()
        self._ready = False

    def _git(self, arguments: list[str], **options: object) -> bytes:
        return run_git(arguments, scheme=self.scheme, git_dir=self.git_dir, **options)  # type: ignore[arg-type]

    def ensure(self) -> None:
        """Start every instance from a fresh bare repository created by this process.

        A repository already on disk is never reused: it may have been committed
        into the project, and its config, alternates or links would steer git.
        """
        if self._ready:
            return
        cache = self.cache.absolute()
        with directory(cache.parent, cache.name, create=True) as fd:
            try:
                info = os.stat("repo.git", dir_fd=fd, follow_symlinks=False)
            except FileNotFoundError:
                pass
            else:
                if not stat.S_ISDIR(info.st_mode):
                    raise WorkflowError("unsafe_path", "registry 缓存仓库不是普通目录")
                shutil.rmtree("repo.git", dir_fd=fd)
            os.mkdir("repo.git", mode=0o700, dir_fd=fd)
        with directory(cache, "repo.git"):
            run_git(["init", "-q", "--bare", "--", str(self.git_dir)], scheme=self.scheme)
        self._ready = True

    def resolve_target(self) -> Target:
        self.ensure()
        if self.spec.version == "latest":
            data = self._git(["ls-remote", "--", self.spec.url, "HEAD", "refs/tags/*"], timeout=60)
            head, tags = parse_ls_remote(data)
            return select_latest(head, tags)
        tag = self.spec.version
        data = self._git(
            ["ls-remote", "--", self.spec.url, "refs/tags/" + tag, "refs/tags/" + tag + "^{}"],
            timeout=60,
        )
        _, tags = parse_ls_remote(data)
        if tag not in tags:
            raise WorkflowError(
                "registry_fetch_failed",
                "registry 中不存在配置的版本 tag",
                "确认 registry.version 对应的 tag 已推送到 registry。",
            )
        return Target(commit=tags[tag], tag=tag, ref="refs/tags/" + tag)

    def fetch(self, target: Target) -> None:
        self.ensure()
        self._git(
            [
                "fetch",
                "-q",
                "--no-tags",
                "--no-write-fetch-head",
                "--depth=1",
                "--",
                self.spec.url,
                f"+{target.ref}:{UPSTREAM_REF}",
            ],
            timeout=300,
        )
        fetched = (
            self._git(["rev-parse", "--verify", "--end-of-options", UPSTREAM_REF + "^{commit}"])
            .decode("ascii", "replace")
            .strip()
        )
        if fetched != target.commit:
            raise WorkflowError(
                "registry_fetch_failed",
                "registry 在预检与拉取之间发生了变化",
                "重新运行 loopspec registry update。",
            )

    def has_commit(self, commit: str) -> bool:
        if not COMMIT_RE.fullmatch(commit):
            return False
        try:
            self._git(["cat-file", "-e", "--end-of-options", commit + "^{commit}"])
        except WorkflowError:
            return False
        return True

    def fetch_base(self, commit: str, tag: str | None = None) -> bool:
        """Best effort: the base only feeds merge context, classification uses lock hashes."""
        if self.has_commit(commit):
            return True
        if tag is not None:
            try:
                self._git(
                    [
                        "fetch",
                        "-q",
                        "--no-tags",
                        "--no-write-fetch-head",
                        "--depth=1",
                        "--",
                        self.spec.url,
                        f"+refs/tags/{check_tag(tag)}:{BASE_REF}",
                    ],
                    timeout=300,
                )
            except (WorkflowError, ValueError):
                pass
            if self.has_commit(commit):
                return True
        try:
            self._git(
                [
                    "fetch",
                    "-q",
                    "--no-tags",
                    "--no-write-fetch-head",
                    "--depth=1",
                    "--",
                    self.spec.url,
                    f"+{commit}:{BASE_REF}",
                ],
                timeout=300,
            )
        except WorkflowError:
            return False
        return self.has_commit(commit)

    def read_tree(self, commit: str) -> RemoteTree:
        if not COMMIT_RE.fullmatch(commit):
            raise WorkflowError("registry_invalid", "commit 不合法")
        treeish = commit + (":" + self.spec.path if self.spec.path else "^{tree}")
        try:
            listing = self._git(
                ["ls-tree", "-r", "-z", "-l", "--end-of-options", treeish], code="registry_invalid"
            )
        except WorkflowError as exc:
            raise WorkflowError(
                "registry_invalid",
                "registry 中不存在 registry.path 指定的目录",
                "检查 registry.path。",
            ) from exc
        tree = RemoteTree()
        blobs: dict[str, tuple[str, int]] = {}
        definitions: set[str] = set()
        candidates: dict[str, tuple[str, str, int]] = {}
        invalid = 0
        for entry in listing.split(b"\0"):
            if not entry:
                continue
            meta, sep, raw_path = entry.partition(b"\t")
            fields = meta.decode("ascii", "replace").split()
            if not sep or len(fields) != 4:
                raise WorkflowError("registry_invalid", "registry 树格式无法解析")
            mode, kind, oid, size = fields
            try:
                path = _registry_path(raw_path.decode("utf-8"))
            except (UnicodeDecodeError, ValueError, WorkflowError):
                invalid += 1
                continue
            if path is None:
                continue
            if kind == "blob" and mode in ("100644", "100755") and size.isdigit():
                candidates[path] = (mode, oid, int(size))
                if (
                    path.startswith("fragments/")
                    and path.count("/") == 2
                    and path.endswith("/fragment.yaml")
                ):
                    definitions.add(path.split("/")[1])
            else:
                tree.unsupported.append(path)
        for path, (_, blob, length) in candidates.items():
            if path.startswith("fragments/") and path.split("/")[1] not in definitions:
                continue
            blobs[path] = (blob, length)
        tree.unsupported = sorted(
            p
            for p in tree.unsupported
            if p.startswith("profiles/") or p.split("/")[1] in definitions
        )
        if invalid:
            tree.warnings.append(f"registry 中有 {invalid} 个名称不合法的条目已忽略")
        if len(blobs) > MAX_FILES:
            raise WorkflowError("registry_invalid", "registry 文件数超过限额")
        if any(length > MAX_FILE_BYTES for _, length in blobs.values()):
            raise WorkflowError("registry_invalid", "registry 中有文件超过单文件限额")
        if sum(length for _, length in blobs.values()) > MAX_BUNDLE_BYTES:
            raise WorkflowError("registry_invalid", "registry 内容超过总量限额")
        tree.files = self._read_blobs(blobs)
        return tree

    def _read_blobs(self, blobs: dict[str, tuple[str, int]]) -> dict[str, bytes]:
        if not blobs:
            return {}
        order = sorted(blobs)
        request = "".join(blobs[path][0] + "\n" for path in order).encode("ascii")
        data = self._git(["cat-file", "--batch"], stdin=request, code="registry_invalid")
        files: dict[str, bytes] = {}
        offset = 0
        for path in order:
            oid, size = blobs[path]
            end = data.find(b"\n", offset)
            if end < 0:
                raise WorkflowError("registry_invalid", "registry 对象输出被截断")
            header = data[offset:end].decode("ascii", "replace").split()
            if header != [oid, "blob", str(size)]:
                raise WorkflowError("registry_invalid", "registry 对象与树不一致")
            content = data[end + 1 : end + 1 + size]
            if len(content) != size or data[end + 1 + size : end + 2 + size] != b"\n":
                raise WorkflowError("registry_invalid", "registry 对象输出被截断")
            files[path] = content
            offset = end + 2 + size
        return files


def safe_segments(path: str) -> bool:
    return all(SEGMENT_RE.fullmatch(part) and part not in (".", "..") for part in path.split("/"))


def _registry_path(path: str) -> str | None:
    """Normalise a registry-relative path; `None` for paths outside fragments/profiles."""
    parts = path.split("/")
    if parts[0] in ("fragments", "profiles") and not safe_segments(path):
        raise ValueError("路径包含不允许的字符")
    if parts[0] == "fragments":
        if len(parts) < 3:
            return None
        if not re.fullmatch(KEBAB_RE, parts[1]) or len(parts) - 2 > MAX_DEPTH:
            raise ValueError("fragment 路径不合法")
        if any(part == ".git" for part in parts):
            raise ValueError("fragment 路径不合法")
        return relative_path(path)
    if parts[0] == "profiles":
        if len(parts) != 2:
            return None
        if not parts[1].endswith(".yaml"):
            return None
        if not re.fullmatch(KEBAB_RE, parts[1][:-5]):
            raise ValueError("profile 名称不合法")
        return path
    return None
