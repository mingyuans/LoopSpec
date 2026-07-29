"""Checkbox progress for nodes that declare `tracks`.

A node may point `tracks` at a checkbox-bearing artifact (typically `tasks.md`).
Parsing is deliberately best-effort and never raises: a missing or unreadable
tracked file reads as "no tasks", which the state machine treats as "not done".
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_CHECKBOX_RE = re.compile(r"^[-*]\s*\[([ xX])\]\s*(.+?)\s*$")


@dataclass(frozen=True)
class TaskItem:
    id: int
    description: str
    done: bool


@dataclass(frozen=True)
class TaskProgress:
    path: str
    resolved_path: Path
    tasks: list[TaskItem] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.tasks)

    @property
    def complete(self) -> int:
        return sum(1 for task in self.tasks if task.done)

    @property
    def remaining(self) -> int:
        return self.total - self.complete


def parse_tasks(text: str) -> list[TaskItem]:
    """Extract `- [ ]` / `- [x]` (or `*`-prefixed) task lines, numbered from 1."""

    tasks: list[TaskItem] = []
    for line in text.splitlines():
        match = _CHECKBOX_RE.match(line.strip())
        if match is None:
            continue
        tasks.append(
            TaskItem(
                id=len(tasks) + 1,
                description=match.group(2),
                done=match.group(1).lower() == "x",
            )
        )
    return tasks


def read_task_progress(artifact_dir: Path, tracks: str) -> TaskProgress:
    """Read progress for `tracks`; a missing/unreadable file yields zero tasks."""

    target = artifact_dir / tracks
    try:
        text = target.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        text = ""
    return TaskProgress(path=tracks, resolved_path=target.resolve(), tasks=parse_tasks(text))


def tracked_work_complete(progress: TaskProgress) -> bool:
    """True only when the tracked file has tasks and every one of them is ticked."""

    return progress.total > 0 and progress.remaining == 0


def progress_summary(progress: TaskProgress) -> dict[str, Any]:
    """Counts only -- what `loopspec status` reports per node."""

    return {
        "path": progress.path,
        "resolvedPath": str(progress.resolved_path),
        "total": progress.total,
        "complete": progress.complete,
        "remaining": progress.remaining,
    }


def progress_detail(progress: TaskProgress) -> dict[str, Any]:
    """Counts plus the task list -- what `loopspec instructions` returns."""

    return {
        **progress_summary(progress),
        "tasks": [
            {"id": task.id, "description": task.description, "done": task.done}
            for task in progress.tasks
        ],
    }
