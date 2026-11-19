"""Keep a project's loopspec skill/command files in step with the installed CLI.

Every workflow command (anything taking `--home`) calls `sync_project_skills` first. For
each AI tool the project already has loopspec skills for, every skill/command file this
CLI would write inside the project is compared byte for byte with what is on disk; a
missing or different file is rewritten. Tools that are not configured are left alone,
files outside the project (Codex's global prompts) are never touched, and nothing here
may break the command it runs before.
"""

from __future__ import annotations

import os
import stat
import sys
from dataclasses import dataclass, field
from pathlib import Path

from .errors import LoopspecError
from .scaffold import expected_files, tool_is_configured
from .tool_registry import AI_TOOLS
from .workflow_io import atomic_write


@dataclass
class SyncResult:
    updated: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)


def project_root(home: Path) -> Path:
    """Where `loopspec init` puts the AI tool files by default: the home's parent."""
    return home.resolve().parent


def managed_files(project: Path) -> dict[str, str]:
    """`project-relative path -> expected content` for every configured tool, in-project only."""
    files: dict[str, str] = {}
    for tool_id in AI_TOOLS:
        if not tool_is_configured(project, tool_id):
            continue
        for path, content in expected_files(project, tool_id).items():
            if path.is_relative_to(project):
                files[path.relative_to(project).as_posix()] = content
    return files


def all_managed_files(project: Path) -> dict[str, str]:
    """Like `managed_files`, for every tool whether configured or not (Diff exclusion)."""
    files: dict[str, str] = {}
    for tool_id in AI_TOOLS:
        for path, content in expected_files(project, tool_id).items():
            if path.is_relative_to(project):
                files[path.relative_to(project).as_posix()] = content
    return files


def _current(project: Path, relative: str) -> bytes | None:
    """The file's bytes, or None when missing; raises OSError for anything not a plain file."""
    path = project / relative
    try:
        info = os.lstat(path)
    except FileNotFoundError:
        return None
    if not stat.S_ISREG(info.st_mode):
        raise OSError(f"{relative} is not a regular file")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, "rb") as stream:
        return stream.read()


def sync_project_skills(home: Path) -> SyncResult:
    result = SyncResult()
    if not home.is_dir():
        return result
    project = project_root(home)
    for relative, content in sorted(managed_files(project).items()):
        data = content.encode("utf-8")
        try:
            if _current(project, relative) == data:
                continue
            # Opens every directory from the root with O_NOFOLLOW and writes through the
            # final directory's descriptor: a symlink anywhere on the way is refused.
            atomic_write(project, relative, data)
        except (OSError, LoopspecError):
            result.skipped.append(relative)
            continue
        result.updated.append(relative)
    return result


def sync_before_command(home: Path) -> None:
    """Sync and report on stderr; never raises, never touches stdout (JSON output)."""
    from . import __version__

    try:
        result = sync_project_skills(home)
    except Exception as exc:  # noqa: BLE001 - must never break the command itself
        print(f"loopspec: skill sync skipped ({type(exc).__name__})", file=sys.stderr)
        return
    if result.updated:
        print(
            f"loopspec: synced {len(result.updated)} skill file(s) with loopspec "
            f"{__version__}: " + ", ".join(result.updated),
            file=sys.stderr,
        )
    if result.skipped:
        print(
            "loopspec: could not sync (not a regular file or unsafe path): "
            + ", ".join(result.skipped),
            file=sys.stderr,
        )
