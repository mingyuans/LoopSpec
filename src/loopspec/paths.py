"""Workflow home / change / artifact root path resolution and safety checks."""

from __future__ import annotations

import re
from pathlib import Path

from .errors import ConfigValidationError, InvalidChangeNameError

_ISSUE_PREFIX_RE = re.compile(r"^([a-z][a-z0-9]*-\d+)(?:-|$)")


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


def reusable_change_name(
    workflow_home: Path,
    artifacts_dir: str,
    requested_name: str,
    schema_name: str | None = None,
) -> str:
    """Return an unambiguous existing canonical name for ``requested_name``.

    Agents commonly append the workflow role to the same ticket, producing
    names such as ``afd-13592-listing-filter-be`` for the ``be-driven`` schema.
    Prefer an exact schema-suffix match, then a unique issue-key match.  If more
    than one existing change is plausible, preserve the requested name instead
    of silently merging unrelated work.
    """

    safe_change_name(requested_name)
    names = _known_change_names(workflow_home, artifacts_dir)
    if requested_name in names:
        return requested_name

    aliases: list[str] = []
    if schema_name:
        aliases.append(schema_name)
        first_token = schema_name.split("-", 1)[0]
        if first_token not in aliases:
            aliases.append(first_token)
    for alias in aliases:
        suffix = f"-{alias}"
        if requested_name.endswith(suffix):
            base = requested_name[: -len(suffix)]
            if base in names:
                return base

    issue_match = _ISSUE_PREFIX_RE.match(requested_name)
    if issue_match is not None:
        issue_prefix = issue_match.group(1)
        matches = sorted(
            name
            for name in names
            if (candidate := _ISSUE_PREFIX_RE.match(name)) is not None
            and candidate.group(1) == issue_prefix
        )
        if len(matches) == 1:
            return matches[0]

    return requested_name


def _known_change_names(workflow_home: Path, artifacts_dir: str) -> set[str]:
    """Safe directory names seen in the active area or an archive month."""

    roots = [artifacts_root(workflow_home, artifacts_dir)]
    archive = workflow_home / "archive"
    if archive.is_dir():
        roots.extend(sorted(path for path in archive.iterdir() if path.is_dir()))

    names: set[str] = set()
    for root in roots:
        if not root.is_dir() or not contained_in(workflow_home, root):
            continue
        for candidate in root.iterdir():
            if not candidate.is_dir() or not contained_in(workflow_home, candidate):
                continue
            if is_safe_relative_path(candidate.name):
                names.add(candidate.name)
    return names


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
