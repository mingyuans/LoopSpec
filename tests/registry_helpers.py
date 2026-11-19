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


def registry_project(
    tmp_path: Path, *, version: str = "latest", tag: str | None = "v1.0.0", path: str = ""
) -> tuple[Path, Path]:
    """A registry plus a Git project whose workflow home uses it and holds no definitions."""
    from tests.workflow_helpers import init_repository

    registry = make_registry(tmp_path / "registry", path=path)
    commit(registry, "release", tag=tag)
    project = tmp_path / "project"
    project.mkdir()
    init_repository(project)
    home = project / "loopspec"
    home.mkdir()
    lines = ["workflow: {}", "registry:", f"  url: {url(registry)}", f"  version: {version}"]
    if path:
        lines.append(f"  path: {path}")
    (home / "config.yaml").write_text("\n".join(lines) + "\n")
    return registry, home


def sync(home: Path) -> dict:
    """`registry update` + `registry apply` as a confirmed human would run them."""
    from loopspec.registry_sync import apply, update

    plan = update(home)
    assert plan["planId"], plan
    return apply(home, plan["planId"])


def add_fragment(registry: Path, name: str, *, base: str = "") -> None:
    root = registry / base if base else registry
    source = root / "fragments" / "requirements"
    target = root / "fragments" / name
    shutil.copytree(source, target)
    definition = target / "fragment.yaml"
    definition.write_text(definition.read_text().replace("name: requirements", f"name: {name}"))


def local_fragment(home: Path, name: str) -> None:
    """A project-only Fragment copied from the built-in `requirements`."""
    target = home / "fragments" / name
    shutil.copytree(builtin_root() / "fragments" / "requirements", target)
    definition = target / "fragment.yaml"
    definition.write_text(definition.read_text().replace("name: requirements", f"name: {name}"))
