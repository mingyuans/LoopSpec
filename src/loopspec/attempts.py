"""Reading .attempts/round-* history and constructing priorAttempts."""

from __future__ import annotations

from fnmatch import fnmatch
from pathlib import Path
from typing import Any

import yaml

from .models import NodeSpec
from .outputs import is_glob, node_output_patterns


def list_rounds(change_dir: Path) -> list[dict[str, Any]]:
    """All recorded rollback rounds for this change, sorted by round number ascending."""

    attempts_dir = change_dir / ".attempts"
    if not attempts_dir.is_dir():
        return []

    rounds: list[dict[str, Any]] = []
    for round_dir in sorted(attempts_dir.glob("round-*")):
        meta_path = round_dir / "_meta.yaml"
        if not meta_path.is_file():
            continue
        meta = yaml.safe_load(meta_path.read_text(encoding="utf-8")) or {}
        meta["_dir"] = round_dir
        rounds.append(meta)

    rounds.sort(key=lambda meta: meta.get("round", 0))
    return rounds


def _matches_pattern(file_path: str, pattern: str) -> bool:
    if is_glob(pattern):
        return fnmatch(file_path, pattern)
    return file_path == pattern


def prior_attempts_for_node(change_dir: Path, node: NodeSpec) -> list[dict[str, Any]]:
    """Build the `priorAttempts` array for a node from its rollback history."""

    patterns = node_output_patterns(node)
    attempts: list[dict[str, Any]] = []
    for meta in list_rounds(change_dir):
        archived_files: list[str] = meta.get("archived_files") or []
        round_dir: Path = meta["_dir"]
        for archived_file in archived_files:
            if not any(_matches_pattern(archived_file, pattern) for pattern in patterns):
                continue
            attempts.append(
                {
                    "round": meta.get("round"),
                    "gate": meta.get("gate"),
                    "verdict": meta.get("verdict"),
                    "summary": meta.get("summary"),
                    "blockingIssues": meta.get("blocking_issues") or [],
                    "archivedPath": str((round_dir / archived_file).resolve()),
                }
            )
    return attempts
