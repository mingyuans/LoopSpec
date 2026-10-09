"""Git 输入边界；仅固定子命令与参数数组，不执行 Shell 或工作区代码。"""

from __future__ import annotations

import os
import re
import selectors
import subprocess
import time
from pathlib import Path

from .errors import WorkflowError


def git(root: Path, arguments: list[str], *, limit: int = 16 * 1024 * 1024) -> bytes:
    environment = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    environment.update(
        {
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_NO_LAZY_FETCH": "1",
            "LC_ALL": "C",
        }
    )
    try:
        process = subprocess.Popen(
            [
                "git",
                "--no-optional-locks",
                "--literal-pathspecs",
                "-c",
                "core.fsmonitor=false",
                "-c",
                "core.hooksPath=" + os.devnull,
                "-c",
                "diff.external=",
                "-C",
                str(root),
                *arguments,
            ],
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        assert process.stdout
        data = bytearray()
        deadline = time.monotonic() + 30
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ)
            while selector.get_map():
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise subprocess.TimeoutExpired("git", 30)
                for key, _ in selector.select(min(remaining, 0.25)):
                    piece = os.read(key.fd, min(65536, limit + 1 - len(data)))
                    if not piece:
                        selector.unregister(key.fileobj)
                    data.extend(piece)
                    if len(data) > limit:
                        raise WorkflowError("resource_limit", "Git 输出超过读取限制")
            process.wait(timeout=max(0.001, deadline - time.monotonic()))
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise WorkflowError("git_input_error", "Git 输入无法读取") from exc
    finally:
        if "process" in locals():
            if process.poll() is None:
                process.kill()
                process.wait()
            if process.stdout:
                process.stdout.close()
    if process.returncode:
        raise WorkflowError("git_input_error", "Git 命令失败，检查仓库及固定基线")
    return bytes(data)


def fixed_baseline(project: Path, requested: str | None = None) -> tuple[str, str]:
    if requested is not None and not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", requested):
        raise WorkflowError("invalid_baseline", "显式基线必须是完整 Commit 哈希")
    try:
        repository = (
            git(project, ["rev-parse", "--show-toplevel"]).decode("utf-8").removesuffix("\n")
        )
        commit = (
            git(
                project,
                ["rev-parse", "--verify", "--end-of-options", (requested or "HEAD") + "^{commit}"],
            )
            .decode("ascii")
            .strip()
        )
    except UnicodeError as exc:
        raise WorkflowError("git_input_error", "Git 路径或基线编码不支持") from exc
    if not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", commit):
        raise WorkflowError("invalid_baseline", "基线不是有效 Commit")
    return commit, str(Path(repository).resolve())
