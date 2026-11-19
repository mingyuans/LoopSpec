"""Archive whole Changes: re-derive status and evidence first, then move only the Change dir.

Rework records (`plans/<NNN>/.attempts/`) and Gate products (`.gates/`, `.gate-rounds/`
and the PASS/FAIL reports a Plan's Gates declare) only matter while a Plan runs, so they
are dropped from the archived copy once the move has succeeded.
"""

from __future__ import annotations

import os
import re
import shutil
import stat
from datetime import UTC, date, datetime
from pathlib import Path

from .errors import WorkflowError
from .workflow_io import directory, relative_path, write_lock
from .workflow_models import CHANGE_RE
from .workflow_state import change_root, changes_dir, plan_ids, read_plan

ATTEMPTS = ".attempts"
#: Per-Plan control directories that only serve a running Plan.
RUNTIME_DIRS = (ATTEMPTS, ".gates", ".gate-rounds")
_DIRECTORY = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW


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
        drops = archive_drops(root)
        if dry_run:
            result["dropped"] = drops
            return result
        # Dropped only after the move succeeded (a crash before it must not lose a running
        # Plan's records), through the moved directory itself, never by path.
        dropped, failed = move(home, root, destination, name, drops)
        result["moved"] = True
        result["dropped"] = dropped
        if failed:
            result["notDropped"] = failed
        return result


def gate_reports(root: Path, plan_id: str) -> list[str]:
    """PASS/FAIL report paths the Plan's Gates declare, relative to the Plan directory."""
    try:
        nodes = read_plan(root, plan_id).spec.nodes
    except WorkflowError:
        return []  # unreadable plan.yaml: keep its reports, still drop control dirs
    paths = set()
    for node in nodes:
        if node.gate:
            for path in (node.gate.outputs.pass_, node.gate.outputs.fail):
                try:
                    path = relative_path(path)
                except WorkflowError:
                    continue
                # Only reports inside artifacts/: never plan.yaml, state.md or control files.
                if path.startswith("artifacts/"):
                    paths.add(path)
    return sorted(paths)


def archive_drops(root: Path) -> list[str]:
    """Everything archiving drops, relative to the Change directory, for every Plan."""
    found = []
    for plan_id in plan_ids(root):
        base = f"plans/{plan_id}"
        for name in RUNTIME_DIRS:
            if os.path.lexists(root / base / name):
                found.append(f"{base}/{name}")
        for report in gate_reports(root, plan_id):
            if os.path.lexists(root / base / report):
                found.append(f"{base}/{report}")
    return found


def _open_parent(rootfd: int, parts: list[str]) -> int:
    """Open `parts` below `rootfd` one component at a time, never following symlinks."""
    current = os.dup(rootfd)
    try:
        for part in parts:
            following = os.open(part, _DIRECTORY, dir_fd=current)
            os.close(current)
            current = following
    except OSError:
        os.close(current)
        raise
    return current


def _prune(rootfd: int, parts: list[str], stop: int) -> None:
    """Remove directories emptied by a deletion, deepest first, keeping `parts[:stop]`."""
    for depth in range(len(parts), stop, -1):
        try:
            parent = _open_parent(rootfd, parts[: depth - 1])
        except OSError:
            return
        try:
            os.rmdir(parts[depth - 1], dir_fd=parent)
        except OSError:
            return  # not empty (or gone): stop climbing
        finally:
            os.close(parent)


def drop_paths(rootfd: int, paths: list[str]) -> tuple[list[str], list[str]]:
    """Delete the given entries under the Change directory open as `rootfd`.

    Every component is opened relative to that descriptor without following symlinks, so
    only the directory that was just moved is touched; a symlink is removed itself, never
    its target. Directories emptied by removing a Gate report are pruned up to (not
    including) the Plan's `artifacts/`. Failures are reported, not raised: the Change is
    already archived and a leftover file does not affect it.
    """
    dropped, failed = [], []
    for path in paths:
        parts = path.split("/")
        try:
            parent = _open_parent(rootfd, parts[:-1])
            try:
                info = os.stat(parts[-1], dir_fd=parent, follow_symlinks=False)
                if stat.S_ISDIR(info.st_mode):
                    shutil.rmtree(parts[-1], dir_fd=parent)
                else:
                    os.unlink(parts[-1], dir_fd=parent)
            finally:
                os.close(parent)
        except (OSError, RecursionError):
            failed.append(path)
            continue
        dropped.append(path)
        if len(parts) > 4 and parts[2] == "artifacts":
            _prune(rootfd, parts[:-1], stop=3)
    return dropped, failed


def move(
    home: Path, root: Path, destination: Path, name: str, drops: list[str] | None = None
) -> tuple[list[str], list[str]]:
    """Rename the Change directory into the archive, then drop `drops` inside it."""
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
                moved = os.stat(name, dir_fd=targetfd, follow_symlinks=False)
        if (moved.st_dev, moved.st_ino) != (original.st_dev, original.st_ino):
            # Something else was renamed into the archive: touch nothing; the identity
            # check of `directory()` reports the concurrent change on exit.
            return [], list(drops or [])
        # `rootfd` is the directory that now sits in the archive.
        return drop_paths(rootfd, drops or [])


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
