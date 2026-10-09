"""Archive whole Changes: re-derive status and evidence first, then move only the Change dir."""

from __future__ import annotations

import os
import re
import stat
from datetime import UTC, date, datetime
from pathlib import Path

from .errors import WorkflowError
from .workflow_io import directory, write_lock
from .workflow_models import CHANGE_RE
from .workflow_state import change_root, changes_dir


def archive(home: Path, name: str, *, force: bool, dry_run: bool, today: date) -> dict:
    from .workflow_changes import status

    root = change_root(home, name)
    destination = home / f"archive/{today:%Y-%m}/{name}"
    with write_lock(root, relocated_root=destination):
        from .workflow_attempts import settle
        from .workflow_state import LoadedPlan, open_change

        ctx = open_change(home, name)
        active = ctx.active_plan()
        if active is not None and not dry_run:
            settle(LoadedPlan(ctx, active, ctx.documents()[active]))
        try:
            report = status(home, name)
            state, complete = report["status"], report["isComplete"]
        except WorkflowError as exc:
            if not force:
                raise
            state, complete = exc.code, False
        if not complete and not force:
            raise WorkflowError(
                "archive_unsafe",
                f"需求状态为 {state}，未完成或证据已过期，不能作为完成需求归档",
                "用 loopspec-continue 推进到 complete；只有人明确要求放弃该需求时才用 --force。",
            )
        result = {
            "changeName": name,
            "dryRun": dry_run,
            "status": state,
            "complete": complete,
            "forced": not complete,
            "source": str(root.absolute()),
            "destination": str(destination.absolute()),
        }
        if not complete:
            result["message"] = "未完成归档：该需求未完成，按人的明确要求放弃并归档。"
        if dry_run:
            return result
        move(home, root, destination, name)
        result["moved"] = True
        return result


def move(home: Path, root: Path, destination: Path, name: str) -> None:
    source_parent = root.parent.relative_to(home).as_posix()
    target_parent = destination.parent.relative_to(home).as_posix()
    with directory(root, relocated_root=destination) as rootfd:
        original = os.fstat(rootfd)
        with directory(home, source_parent) as sourcefd:
            with directory(home, target_parent, create=True) as targetfd:
                try:
                    os.stat(name, dir_fd=targetfd, follow_symlinks=False)
                except FileNotFoundError:
                    pass
                else:
                    raise WorkflowError("archive_conflict", "归档目标已存在，不能覆盖")
                current = os.stat(name, dir_fd=sourcefd, follow_symlinks=False)
                if not stat.S_ISDIR(current.st_mode) or (original.st_dev, original.st_ino) != (
                    current.st_dev,
                    current.st_ino,
                ):
                    raise WorkflowError("concurrent_path_change", "需求目录在归档前变化")
                os.rename(name, name, src_dir_fd=sourcefd, dst_dir_fd=targetfd)
                os.fsync(sourcefd)
                os.fsync(targetfd)


def archive_all(home: Path, *, older_than: int | None, dry_run: bool, today: date) -> dict:
    from .workflow_state import read_state

    parent = changes_dir(home)
    try:
        with directory(home, parent) as fd:
            names = sorted(
                item
                for item in os.listdir(fd)
                if re.fullmatch(CHANGE_RE, item)
                and stat.S_ISDIR(os.stat(item, dir_fd=fd, follow_symlinks=False).st_mode)
            )
    except WorkflowError as exc:
        if not isinstance(exc.__cause__, FileNotFoundError):
            raise
        names = []
    archived, skipped = [], []
    for name in names:
        try:
            if older_than is not None:
                created = datetime.fromisoformat(read_state(home / parent / name).created)
                if created.tzinfo is None:
                    created = created.replace(tzinfo=UTC)
                if (datetime.now(UTC) - created).days < older_than:
                    skipped.append({"changeName": name, "reason": "too_recent"})
                    continue
            archived.append(archive(home, name, force=False, dry_run=dry_run, today=today))
        except WorkflowError as exc:
            skipped.append({"changeName": name, "reason": exc.code})
        except ValueError:
            skipped.append({"changeName": name, "reason": "workflow_invalid"})
    return {"dryRun": dry_run, "archived": archived, "skipped": skipped}
