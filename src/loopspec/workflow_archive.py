"""Archive whole Changes in two steps, with the memory review as part of the protocol.

`prepare` re-derives status and evidence, archives nothing, and issues an archive ticket
(`archiveId`) bound to each Change's content and to the memory topics, together with the
review instructions and the inputs to read. `confirm` takes the ticket plus the review
outcome (`--memory updated|none` and a note), re-checks everything under the Change locks,
checks the outcome against the memory topics, records it in the Change `state.md`, then
moves the Change into the archive.

Rework records (`plans/<NNN>/.attempts/`) and Gate products (`.gates/`, `.gate-rounds/`
and the PASS/FAIL reports a Plan's Gates declare) only matter while a Plan runs, so they
are dropped from the archived copy once the move has succeeded.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import stat
from contextlib import ExitStack
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Literal

from .errors import WorkflowError
from .workflow_io import (
    append_text,
    atomic_write,
    canonical,
    digest,
    directory,
    exists,
    read_bytes,
    relative_path,
    unlink_file,
    write_lock,
)
from .workflow_models import CHANGE_RE
from .workflow_state import change_root, changes_dir, plan_ids, read_plan

ATTEMPTS = ".attempts"
#: Per-Plan control directories that only serve a running Plan.
RUNTIME_DIRS = (ATTEMPTS, ".gates", ".gate-rounds")
_DIRECTORY = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
TICKETS = ".cache/archive"
ID_RE = re.compile(r"^[0-9a-f]{64}$")
CONTENT_SCAN_MAX = 20000
INPUT_LIMIT = 500
Review = Literal["updated", "none"]


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


# ---------------------------------------------------------------- snapshots


def content_digest(root: Path) -> str:
    """Digest of everything in a Change directory (not following symlinks), lock file aside."""
    entries: list[list[str]] = []
    for current, dirs, files in os.walk(root, followlinks=False):
        dirs.sort()
        for name in sorted(files) + [d for d in dirs if os.path.islink(os.path.join(current, d))]:
            path = os.path.join(current, name)
            relative = os.path.relpath(path, root).replace(os.sep, "/")
            if relative.endswith(".write.lock"):
                continue
            if len(entries) >= CONTENT_SCAN_MAX:
                raise WorkflowError("resource_limit", "Change 目录条目超过限制")
            info = os.lstat(path)
            if stat.S_ISREG(info.st_mode):
                hashed = hashlib.sha256()
                fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
                with os.fdopen(fd, "rb") as stream:
                    for piece in iter(lambda: stream.read(1 << 20), b""):
                        hashed.update(piece)
                entries.append([relative, "file", hashed.hexdigest()])
            else:
                entries.append([relative, stat.filemode(info.st_mode)[0]])
    return digest(entries)


def memory_snapshot(home: Path) -> dict[str, str]:
    """`topic -> sha256` of the valid memory topics, read the way `loopspec memory` reads them."""
    from .workflow_memory import _read_file, _scan

    topics, _ = _scan(home)
    return {topic: hashlib.sha256(_read_file(home, topic)).hexdigest() for topic in topics}


def memory_changes(before: dict[str, str], after: dict[str, str]) -> list[str]:
    return sorted(t for t in set(before) | set(after) if before.get(t) != after.get(t))


# ------------------------------------------------------------------ tickets


def _ticket_path(archive_id: str) -> str:
    return f"{TICKETS}/{archive_id}.json"


def _identity(ticket: dict) -> dict:
    return {k: ticket[k] for k in ("version", "all", "entries", "memory")}


def _write_ticket(home: Path, archive_id: str, ticket: dict) -> None:
    if not exists(home, TICKETS + "/.gitignore"):
        atomic_write(home, TICKETS + "/.gitignore", b"*\n")
    atomic_write(home, _ticket_path(archive_id), canonical(ticket) + b"\n")


def _read_ticket(home: Path, archive_id: str) -> dict:
    if not ID_RE.fullmatch(archive_id or ""):
        raise WorkflowError("archive_ticket_not_found", "archiveId 格式不正确", _PREPARE_FIX)
    try:
        raw = read_bytes(home, _ticket_path(archive_id))
    except WorkflowError as exc:
        if isinstance(exc.__cause__, FileNotFoundError) or exc.code == "unsafe_path":
            raise WorkflowError(
                "archive_ticket_not_found", "没有这个归档凭据", _PREPARE_FIX
            ) from exc
        raise
    try:
        ticket = json.loads(raw)
        entries = ticket["entries"]
        valid = (
            ticket["version"] == 1
            and isinstance(ticket["all"], bool)
            and isinstance(ticket["memory"], dict)
            and isinstance(ticket.get("progress", {}), dict)
            and all(
                isinstance(e, dict)
                and re.fullmatch(CHANGE_RE, e["change"])
                and isinstance(e["forced"], bool)
                and ID_RE.fullmatch(e["content"])
                for e in entries
            )
            and digest(_identity(ticket)) == archive_id
        )
    except (ValueError, KeyError, TypeError, RecursionError) as exc:
        raise WorkflowError("archive_ticket_invalid", "归档凭据已损坏", _PREPARE_FIX) from exc
    if not valid:
        raise WorkflowError("archive_ticket_invalid", "归档凭据已损坏", _PREPARE_FIX)
    return ticket


_PREPARE_FIX = (
    "重新执行第一段：loopspec change archive <change>（或 --all），用新的 archiveId 确认。"
)


# ---------------------------------------------------------------- review


_FALLBACK_PROCEDURE = (
    "Memory maintenance procedure. Read the inputs, keep only conclusions future changes can "
    "reuse, update existing topics in memory/<topic>.md before creating new ones, write each "
    "entry with when it applies, what to do, why, and its source; record nothing unverified."
)


def review_instructions() -> str:
    """The archive skill's own memory maintenance procedure, so CLI and skill never diverge."""
    from .builtin_resources import builtin_skills_dir

    procedure = _FALLBACK_PROCEDURE
    try:
        text = (builtin_skills_dir() / "archive.md").read_text(encoding="utf-8")
        found = [line for line in text.splitlines() if line.startswith("Memory maintenance")]
        if found:
            procedure = found[0]
    except OSError:
        pass
    return (
        "Before confirming this archive, review the Change for project memory. Read the "
        "inputs listed below now: the Gate reports, Gate evidence and rework records in "
        "`dropped` are deleted by the archive and cannot be read afterwards. Then maintain "
        "memory as follows, and confirm with `--memory updated` if you changed memory topics or "
        "`--memory none` with a note saying why nothing was reusable. The outcome and note are "
        "recorded in the Change state.md. Do not edit memory only to pass the check.\n\n"
        + procedure
    )


def review_inputs(root: Path, drops: list[str]) -> dict:
    states = [str(root / "state.md")]
    artifacts: list[str] = []
    for plan_id in plan_ids(root):
        base = root / "plans" / plan_id
        states.append(str(base / "state.md"))
        for current, dirs, files in os.walk(base / "artifacts", followlinks=False):
            dirs.sort()
            artifacts.extend(str(Path(current) / name) for name in sorted(files))
    return {
        "stateFiles": [p for p in states if os.path.isfile(p)],
        "artifacts": artifacts[:INPUT_LIMIT],
        "artifactsTruncated": len(artifacts) > INPUT_LIMIT,
        "willBeDeleted": [str(root / path) for path in drops],
    }


# ------------------------------------------------------------------- checks


def _recheck(home: Path, name: str, force: bool) -> tuple[str, bool]:
    """Settle leftover rework moves, then re-derive status; `(status, complete)`."""
    from .workflow_attempts import settle
    from .workflow_changes import status
    from .workflow_state import LoadedPlan, open_change

    ctx = open_change(home, name)
    active = ctx.active_plan()
    if active is not None:
        # Finishing a rework move an earlier command committed, not part of archiving.
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
    return state, complete


def _destination(home: Path, name: str, today: date) -> Path:
    return home / f"archive/{today:%Y-%m}/{name}"


# ------------------------------------------------------------------ step 1


def _candidates(home: Path, older_than: int | None) -> tuple[list[str], list[dict]]:
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
    kept, skipped = [], []
    for name in names:
        if older_than is not None:
            try:
                created = datetime.fromisoformat(read_state(home / parent / name).created)
            except (WorkflowError, ValueError) as exc:
                code = exc.code if isinstance(exc, WorkflowError) else "workflow_invalid"
                skipped.append({"changeName": name, "reason": code})
                continue
            if created.tzinfo is None:
                created = created.replace(tzinfo=UTC)
            if (datetime.now(UTC) - created).days < older_than:
                skipped.append({"changeName": name, "reason": "too_recent"})
                continue
        kept.append(name)
    return kept, skipped


def prepare(
    home: Path,
    name: str | None,
    *,
    force: bool,
    all_changes: bool = False,
    older_than: int | None = None,
    today: date,
) -> dict:
    """Step 1: check, archive nothing, issue a ticket and the memory review to do now."""
    if all_changes:
        names, skipped = _candidates(home, older_than)
    else:
        assert name is not None
        names, skipped = [name], []
    entries, changes = [], []
    for item in names:
        root = change_root(home, item)
        destination = _destination(home, item, today)
        try:
            with write_lock(root, relocated_root=destination):
                state, complete = _recheck(home, item, force)
                drops = archive_drops(root)
                content = content_digest(root)
        except WorkflowError as exc:
            if not all_changes:
                raise
            skipped.append({"changeName": item, "reason": exc.code})
            continue
        entries.append({"change": item, "forced": not complete, "content": content})
        change = {
            "changeName": item,
            "status": state,
            "complete": complete,
            "forced": not complete,
            "source": str(root.absolute()),
            "destination": str(destination.absolute()),
            "dropped": drops,
            "inputs": review_inputs(root.absolute(), drops),
        }
        if not complete:
            change["message"] = "未完成归档：该需求未完成，按人的明确要求放弃并归档。"
        changes.append(change)
    result: dict = {"archiveId": None, "changes": changes}
    if all_changes:
        result["skipped"] = skipped
    if not entries:
        result["nextSteps"] = []
        return result
    from .workflow_memory import list_topics

    ticket = {
        "version": 1,
        "all": all_changes,
        "entries": entries,
        "memory": memory_snapshot(home),
    }
    archive_id = digest(ticket)
    _write_ticket(home, archive_id, {**ticket, "created": datetime.now(UTC).isoformat()})
    result["archiveId"] = archive_id
    result["memoryReview"] = {
        "instructions": review_instructions(),
        "memoryIndex": list_topics(home, offset=0, limit=200),
    }
    result["nextSteps"] = [
        f"loopspec change archive --confirm {archive_id} --memory updated|none --note \"<...>\""
    ]
    return result


# ------------------------------------------------------------------ step 2


def confirm(home: Path, archive_id: str, *, memory: Review, note: str, today: date) -> dict:
    """Step 2: re-check under every lock, check the review outcome, record it, then move."""
    from .workflow_journal import memory_review_event
    from .workflow_state import now
    from .workflow_state_notes import MAX_TEXT, _clean

    if memory not in ("updated", "none"):
        raise WorkflowError("workflow_invalid", "--memory 只能是 updated 或 none")
    note = _clean("--note", note, MAX_TEXT)
    ticket = _read_ticket(home, archive_id)
    progress: dict = ticket.setdefault("progress", {})
    pending = sorted(
        (e for e in ticket["entries"] if not progress.get(e["change"], {}).get("archived")),
        key=lambda e: e["change"],
    )
    archived: list[dict] = []
    with ExitStack() as stack:
        for entry in pending:
            name = entry["change"]
            stack.enter_context(
                write_lock(
                    change_root(home, name), relocated_root=_destination(home, name, today)
                )
            )
        for entry in pending:
            name, root = entry["change"], change_root(home, entry["change"])
            _, complete = _recheck(home, name, entry["forced"])
            if not complete and not entry["forced"]:
                raise WorkflowError("archive_ticket_stale", "需求状态已变化", _PREPARE_FIX)
            expected = progress.get(name, {}).get("content", entry["content"])
            if content_digest(root) != expected:
                raise WorkflowError(
                    "archive_ticket_stale", f"第一段之后 Change {name} 的内容已变化", _PREPARE_FIX
                )
            if os.path.lexists(_destination(home, name, today)):
                raise WorkflowError("archive_conflict", "归档目标已存在，不能覆盖")
        changed = memory_changes(ticket["memory"], memory_snapshot(home))
        if memory == "updated" and not changed:
            raise WorkflowError(
                "memory_review_missing",
                "选择了 --memory updated，但 memory/ 中没有任何 topic 变化",
                "按审阅结果更新 memory/<topic>.md 后再确认；确实没有可复用结论时用 --memory none。",
            )
        if memory == "none" and changed:
            raise WorkflowError(
                "memory_review_mismatch",
                "选择了 --memory none，但 memory/ 中有 topic 变化：" + ", ".join(changed),
                "如实使用 --memory updated，或撤销这些改动后再确认。",
            )
        for entry in pending:
            name = entry["change"]
            root = change_root(home, name)
            destination = _destination(home, name, today)
            state = progress.setdefault(name, {})
            if not state.get("recorded"):
                # Strict: if the review cannot be recorded, the Change is not archived.
                append_text(
                    root, "state.md", memory_review_event(now(), name, memory, changed, note)
                )
                state.update(recorded=True, content=content_digest(root))
                _write_ticket(home, archive_id, ticket)
            drops = archive_drops(root)
            dropped, failed = move(home, root, destination, name, drops)
            state["archived"] = True
            _write_ticket(home, archive_id, ticket)
            item = {
                "changeName": name,
                "forced": entry["forced"],
                "moved": True,
                "destination": str(destination.absolute()),
                "dropped": dropped,
            }
            if failed:
                item["notDropped"] = failed
            archived.append(item)
    unlink_file(home, _ticket_path(archive_id))
    return {
        "archiveId": archive_id,
        "memoryReview": {"memory": memory, "note": note, "changedTopics": changed},
        "archived": archived,
    }
