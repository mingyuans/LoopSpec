"""Local git registries for the registry tests: `file://` URLs only, never the network."""

from __future__ import annotations

import shutil
from pathlib import Path

from loopspec.builtin_resources import builtin_root
from loopspec.workflow_git import git


def make_registry(root: Path, *, path: str = "") -> Path:
    """A git repository holding the built-in fragments/profiles under `path`."""
    root.mkdir(parents=True)
    git(root, ["init", "-q", "-b", "main"])
    git(root, ["config", "user.name", "Registry"])
    git(root, ["config", "user.email", "registry@example.invalid"])
    base = root / path if path else root
    for kind in ("fragments", "profiles"):
        shutil.copytree(builtin_root() / kind, base / kind)
    (root / "README.md").write_text("registry\n")
    commit(root, "initial")
    return root


def commit(root: Path, message: str, *, tag: str | None = None, annotated: bool = False) -> str:
    git(root, ["add", "-A"])
    git(root, ["commit", "-q", "--allow-empty", "-m", message])
    if tag:
        extra = ["-a", "-m", tag] if annotated else []
        git(root, ["tag", *extra, tag])
    return git(root, ["rev-parse", "HEAD"]).decode().strip()


def url(root: Path) -> str:
    return "file://" + str(root.resolve())
