"""Workflow home / change / artifact root path resolution and safety checks."""

from __future__ import annotations

from pathlib import Path

from .errors import ConfigValidationError, InvalidChangeNameError


def is_safe_relative_path(path: str) -> bool:
    """A relative path with no absolute component and no `..` traversal."""

    if not path:
        return False
    parsed = Path(path)
    if parsed.is_absolute():
        return False
    return ".." not in parsed.parts


def resolve_within(root: Path, relative: str, *, what: str) -> Path:
    """Resolve `relative` under `root`; raise if unsafe or it escapes `root`."""

    if not is_safe_relative_path(relative):
        raise ConfigValidationError(f"{what} must be a safe relative path: {relative}")
    root_resolved = root.resolve()
    target = (root / relative).resolve()
    if target != root_resolved and root_resolved not in target.parents:
        raise ConfigValidationError(f"{what} must stay within {root}: {relative}")
    return target


def artifacts_root(workflow_home: Path, artifacts_dir: str) -> Path:
    return resolve_within(workflow_home, artifacts_dir, what="artifacts_dir")


def change_root(workflow_home: Path, artifacts_dir: str, change_name: str) -> Path:
    return artifacts_root(workflow_home, artifacts_dir) / change_name


def artifact_root(change_dir: Path, schema_path: str | None) -> Path:
    """The artifact root for a change: the change dir itself, or a schema-declared subdir."""

    if schema_path is None:
        return change_dir
    return resolve_within(change_dir, schema_path, what="schema path")


def schema_dir(workflow_home: Path, schema_name: str) -> Path:
    return workflow_home / "schemas" / schema_name


def archive_root(workflow_home: Path, year_month: str) -> Path:
    return workflow_home / "archive" / year_month


def safe_change_name(change_name: str) -> str:
    """Validate a change name before it is joined onto any directory.

    `change_root` joins the name straight on, so commands that only ever touch
    one location get away with an `is_dir()` check afterwards. `artifacts` joins
    it onto the active directory *and* every archive month, so it validates up
    front instead of relying on each join site to notice.
    """

    if not is_safe_relative_path(change_name):
        raise InvalidChangeNameError(
            f"Invalid change name: {change_name}",
            fix="Use a relative name without `..` path segments.",
        )
    return change_name


def contained_in(root: Path, path: Path) -> bool:
    """Whether `path` resolves to `root` itself or somewhere beneath it.

    Resolves symlinks first, which is the whole point: a link inside a change
    directory pointing at `/etc` resolves outside the workflow home, and a path
    that escapes must never reach the output (design D11).
    """

    root_resolved = root.resolve()
    try:
        target = path.resolve()
    except OSError:
        return False
    return target == root_resolved or root_resolved in target.parents


def archive_locations(workflow_home: Path, change_name: str) -> list[tuple[str, Path]]:
    """`(month, directory)` for every archived copy of this change, oldest first.

    Month directory names are *not* required to look like `YYYY-MM`: an archive
    someone reorganised by hand must not make artifacts vanish, and the safety
    that matters is `contained_in`, not the name's shape (design D2).
    """

    archive_dir = workflow_home / "archive"
    if not archive_dir.is_dir():
        return []

    found: list[tuple[str, Path]] = []
    for month_dir in sorted(p for p in archive_dir.iterdir() if p.is_dir()):
        candidate = month_dir / change_name
        if not candidate.is_dir():
            continue
        if not contained_in(workflow_home, candidate):
            continue
        found.append((month_dir.name, candidate))
    return found
