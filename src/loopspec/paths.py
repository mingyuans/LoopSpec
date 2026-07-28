"""Workflow home / change / artifact root path resolution and safety checks."""

from __future__ import annotations

from pathlib import Path

from .errors import ConfigValidationError


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
