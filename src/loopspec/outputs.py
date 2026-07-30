"""Artifact output resolution from the filesystem."""

from __future__ import annotations

from pathlib import Path

from .models import NodeSpec

GLOB_CHARS = set("*?[")
_RESERVED_NAMES = {".workflow.yaml", "state.md"}


def is_glob(pattern: str) -> bool:
    return any(char in pattern for char in GLOB_CHARS)


def _is_artifact_candidate(path: Path, artifact_dir: Path) -> bool:
    rel_parts = path.relative_to(artifact_dir).parts
    if ".attempts" in rel_parts:
        return False
    if path.name in _RESERVED_NAMES:
        return False
    return True


def resolve_outputs(artifact_dir: Path, generates: str) -> list[Path]:
    """Return the currently existing, resolved output file paths for `generates`."""

    if not is_glob(generates):
        target = artifact_dir / generates
        if target.is_file() and _is_artifact_candidate(target, artifact_dir):
            return [target.resolve()]
        return []
    return sorted(
        path.resolve()
        for path in artifact_dir.glob(generates)
        if path.is_file() and _is_artifact_candidate(path, artifact_dir)
    )


def outputs_exist(artifact_dir: Path, generates: str) -> bool:
    return len(resolve_outputs(artifact_dir, generates)) > 0


def resolved_output_path(artifact_dir: Path, generates: str) -> str | list[str] | None:
    """The wildcard-free absolute path(s) a `generates` pattern points at.

    A concrete path resolves to itself whether or not it exists yet: that is where
    the artifact goes, which is exactly what a node about to be written needs. A
    glob has no such answer up front and can only be resolved from what is on disk
    -- the matches when there are any, and None when there are none, since there
    is no single path to name and a pattern with `*` in it is not one.
    """

    if not is_glob(generates):
        return str((artifact_dir / generates).resolve())
    matches = [str(path) for path in resolve_outputs(artifact_dir, generates)]
    return matches or None


def node_output_patterns(node: NodeSpec) -> list[str]:
    if node.gate is not None:
        patterns = [node.gate.outputs.pass_, node.gate.outputs.fail]
        if node.generates is not None:
            patterns.append(node.generates)
        return patterns
    assert node.generates is not None
    return [node.generates]
