"""Remote git boundary: ls-remote parsing, failure codes and the remote tree reader (D2–D4)."""

from __future__ import annotations

import os
import threading
from pathlib import Path

import pytest

from loopspec.errors import WorkflowError
from loopspec.models import RegistrySpec
from loopspec.registry_git import (
    RegistryRepo,
    parse_ls_remote,
    redact,
    select_latest,
)
from loopspec.workflow_git import git
from tests.registry_helpers import commit, make_registry, url

A = "a" * 40
B = "b" * 40
C = "c" * 40
D = "d" * 40


def repo_for(tmp_path: Path, spec: RegistrySpec) -> RegistryRepo:
    return RegistryRepo(tmp_path / "cache", spec)


# ----------------------------------------------------------------- ls-remote


def test_parse_ls_remote_keeps_only_valid_lines() -> None:
    data = (
        f"{A}\tHEAD\n"
        f"{B}\trefs/tags/v1.0.0\n"
        f"{C}\trefs/tags/v1.1.0\n"
        f"{D}\trefs/tags/v1.1.0^{{}}\n"
        f"{A}\trefs/heads/main\n"
        f"zzzz\trefs/tags/v9.0.0\n"
        f"{A}\trefs/tags/-evil\n"
        f"{A}\trefs/tags/bad\x1bname\n"
        "garbage line\n"
    ).encode()
    head, tags = parse_ls_remote(data)
    assert head == A
    # An annotated tag resolves to the commit it peels to.
    assert tags == {"v1.0.0": B, "v1.1.0": D}


def test_latest_orders_numerically_and_ignores_prereleases() -> None:
    tags = {"v1.9.0": A, "v1.10.0": B, "v2.0.0-rc1": C, "nightly": D}
    target = select_latest(None, tags)
    assert (target.tag, target.commit, target.ref) == ("v1.10.0", B, "refs/tags/v1.10.0")


def test_latest_without_release_tags_tracks_head() -> None:
    target = select_latest(A, {"nightly": B})
    assert (target.tag, target.commit, target.ref) == (None, A, "HEAD")


def test_latest_without_anything_fails() -> None:
    with pytest.raises(WorkflowError) as caught:
        select_latest(None, {})
    assert caught.value.code == "registry_fetch_failed"


def test_resolve_latest_and_fixed_tag(tmp_path: Path) -> None:
    registry = make_registry(tmp_path / "registry")
    first = commit(registry, "v1", tag="v1.0.0", annotated=True)
    (registry / "fragments" / "design" / "extra.md").write_text("x")
    second = commit(registry, "v1.1", tag="v1.1.0")
    latest = repo_for(tmp_path, RegistrySpec(url=url(registry))).resolve_target()
    assert (latest.tag, latest.commit) == ("v1.1.0", second)
    fixed = repo_for(tmp_path, RegistrySpec(url=url(registry), version="v1.0.0")).resolve_target()
    assert (fixed.tag, fixed.commit) == ("v1.0.0", first)


def test_resolve_missing_fixed_tag(tmp_path: Path) -> None:
    registry = make_registry(tmp_path / "registry")
    spec = RegistrySpec(url=url(registry), version="v9.9.9")
    with pytest.raises(WorkflowError) as caught:
        repo_for(tmp_path, spec).resolve_target()
    assert caught.value.code == "registry_fetch_failed"


# ------------------------------------------------------------------ failures


def test_git_missing_is_unavailable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    monkeypatch.setenv("PATH", str(empty))
    with pytest.raises(WorkflowError) as caught:
        repo_for(tmp_path, RegistrySpec(url="file:///nowhere")).resolve_target()
    assert caught.value.code == "registry_unavailable"


def test_unreachable_registry_fails_with_bounded_message(tmp_path: Path) -> None:
    spec = RegistrySpec(url="file://" + str(tmp_path / "missing"))
    with pytest.raises(WorkflowError) as caught:
        repo_for(tmp_path, spec).resolve_target()
    assert caught.value.code == "registry_fetch_failed"
    assert len(caught.value.message) <= 2200


def test_redact_hides_credentials_and_truncates() -> None:
    text = "fatal: https://alice:s3cr3t@host/x\n" + "line\n" * 100
    cleaned = redact(text.encode())
    assert "s3cr3t" not in cleaned and "alice" not in cleaned
    assert cleaned.count("\n") <= 20
    assert len(redact(b"x" * 10000)) <= 2000


def test_environment_cannot_redirect_the_repository(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    registry = make_registry(tmp_path / "registry")
    target_commit = commit(registry, "tagged", tag="v1.0.0")
    monkeypatch.setenv("GIT_DIR", str(tmp_path / "elsewhere"))
    monkeypatch.setenv("GIT_CONFIG_PARAMETERS", "'protocol.allow'='always'")
    repo = repo_for(tmp_path, RegistrySpec(url=url(registry)))
    target = repo.resolve_target()
    repo.fetch(target)
    assert target.commit == target_commit
    assert not (tmp_path / "elsewhere").exists()


# ---------------------------------------------------------------- tree read


def test_fetch_and_read_tree(tmp_path: Path) -> None:
    registry = make_registry(tmp_path / "registry", path="workflows")
    commit(registry, "tagged", tag="v1.0.0")
    repo = repo_for(tmp_path, RegistrySpec(url=url(registry), path="workflows"))
    target = repo.resolve_target()
    repo.fetch(target)
    tree = repo.read_tree(target.commit)
    assert "fragments/qa-testing/fragment.yaml" in tree.files
    assert "profiles/bugfix.yaml" in tree.files
    assert not any(p.startswith(("README", "workflows")) for p in tree.files)
    assert tree.unsupported == [] and tree.warnings == []
    # Nothing is checked out: the cache holds only a bare repository.
    assert not (tmp_path / "cache" / "repo.git" / "fragments").exists()


def test_read_tree_filters_unsafe_entries(tmp_path: Path) -> None:
    registry = make_registry(tmp_path / "registry")
    fragments = registry / "fragments"
    os.symlink("/etc/passwd", fragments / "design" / "leak.md")
    (fragments / "Bad_Name").mkdir()
    (fragments / "Bad_Name" / "fragment.yaml").write_text("x")
    (fragments / "no-definition").mkdir()
    (fragments / "no-definition" / "readme.md").write_text("x")
    (registry / "profiles" / "notes.txt").write_text("x")
    sub = tmp_path / "sub"
    make_registry(sub)
    git(
        registry,
        [
            "-c",
            "protocol.file.allow=always",
            "submodule",
            "add",
            "-q",
            url(sub),
            "fragments/design/vendored",
        ],
    )
    commit(registry, "unsafe", tag="v1.0.0")
    repo = repo_for(tmp_path, RegistrySpec(url=url(registry)))
    target = repo.resolve_target()
    repo.fetch(target)
    tree = repo.read_tree(target.commit)
    assert sorted(tree.unsupported) == [
        "fragments/design/leak.md",
        "fragments/design/vendored",
    ]
    assert not any("Bad_Name" in p or "no-definition" in p for p in tree.files)
    assert "profiles/notes.txt" not in tree.files
    assert tree.warnings and not any("Bad_Name" in w for w in tree.warnings)


def test_read_tree_enforces_size_limit(tmp_path: Path) -> None:
    registry = make_registry(tmp_path / "registry")
    (registry / "fragments" / "design" / "huge.md").write_bytes(b"x" * (2 * 1024 * 1024 + 1))
    commit(registry, "huge", tag="v1.0.0")
    repo = repo_for(tmp_path, RegistrySpec(url=url(registry)))
    target = repo.resolve_target()
    repo.fetch(target)
    with pytest.raises(WorkflowError) as caught:
        repo.read_tree(target.commit)
    assert caught.value.code == "registry_invalid"


def test_read_tree_missing_path(tmp_path: Path) -> None:
    registry = make_registry(tmp_path / "registry")
    commit(registry, "tagged", tag="v1.0.0")
    repo = repo_for(tmp_path, RegistrySpec(url=url(registry), path="nope"))
    target = repo.resolve_target()
    repo.fetch(target)
    with pytest.raises(WorkflowError) as caught:
        repo.read_tree(target.commit)
    assert caught.value.code == "registry_invalid"


def test_has_commit_after_fetch(tmp_path: Path) -> None:
    registry = make_registry(tmp_path / "registry")
    commit(registry, "tagged", tag="v1.0.0")
    repo = repo_for(tmp_path, RegistrySpec(url=url(registry)))
    target = repo.resolve_target()
    assert not repo.has_commit(target.commit)
    repo.fetch(target)
    assert repo.has_commit(target.commit)


# ------------------------------------------------------- security regressions


def test_preplanted_cache_repository_is_never_trusted(tmp_path: Path) -> None:
    """A committed `.cache/registry/repo.git` must not steer git through its config."""
    registry = make_registry(tmp_path / "registry")
    commit(registry, "real", tag="v1.0.0")
    evil = make_registry(tmp_path / "evil")
    (evil / "profiles" / "evil.yaml").write_text(
        (evil / "profiles" / "bugfix.yaml").read_text().replace("name: bugfix", "name: evil")
    )
    commit(evil, "evil", tag="v9.0.0")
    cache = tmp_path / "cache"
    planted = cache / "repo.git"
    git(tmp_path, ["init", "-q", "--bare", str(planted)])
    with (planted / "config").open("a") as config:
        config.write(f'[url "{url(evil)}"]\n\tinsteadOf = {url(registry)}\n')
    repo = RegistryRepo(cache, RegistrySpec(url=url(registry)))
    target = repo.resolve_target()
    repo.fetch(target)
    assert target.tag == "v1.0.0"
    assert "profiles/evil.yaml" not in repo.read_tree(target.commit).files
    assert "insteadOf" not in (planted / "config").read_text()


def test_cache_repository_symlink_is_refused(tmp_path: Path) -> None:
    registry = make_registry(tmp_path / "registry")
    commit(registry, "real", tag="v1.0.0")
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (elsewhere / "keep.txt").write_text("keep")
    cache = tmp_path / "cache"
    cache.mkdir()
    (cache / "repo.git").symlink_to(elsewhere)
    with pytest.raises(WorkflowError) as caught:
        RegistryRepo(cache, RegistrySpec(url=url(registry))).resolve_target()
    assert caught.value.code == "unsafe_path"
    assert (elsewhere / "keep.txt").read_text() == "keep"


@pytest.mark.parametrize(
    "name", ["$(touch pwned).md", "a`id`;b.md", "x‮gpj.md", "with space.md", "q'uote.md"]
)
def test_shell_metacharacters_in_names_are_dropped(tmp_path: Path, name: str) -> None:
    registry = make_registry(tmp_path / "registry")
    (registry / "fragments" / "design" / name).write_text("x")
    commit(registry, "odd", tag="v1.0.0")
    repo = repo_for(tmp_path, RegistrySpec(url=url(registry)))
    target = repo.resolve_target()
    repo.fetch(target)
    tree = repo.read_tree(target.commit)
    assert not any(name in p for p in tree.files)
    assert tree.warnings and not any(name in w for w in tree.warnings)
    assert "fragments/design/fragment.yaml" in tree.files


def test_large_batch_read_completes(tmp_path: Path) -> None:
    """The cat-file request exceeds a pipe buffer while git streams large blobs back."""
    registry = make_registry(tmp_path / "registry")
    bulk = registry / "fragments" / "design" / "bulk"
    bulk.mkdir()
    for index in range(1900):
        (bulk / f"f{index:04d}.md").write_bytes(b"%d" % index * 1000)
    commit(registry, "bulk", tag="v1.0.0")
    repo = repo_for(tmp_path, RegistrySpec(url=url(registry)))
    target = repo.resolve_target()
    repo.fetch(target)
    result: list[int] = []
    worker = threading.Thread(
        target=lambda: result.append(len(repo.read_tree(target.commit).files))
    )
    worker.start()
    worker.join(120)
    assert not worker.is_alive(), "cat-file --batch deadlocked"
    assert result and result[0] > 1900


def test_ssh_user_cannot_start_with_dash() -> None:
    with pytest.raises(ValueError):
        RegistrySpec(url="ssh://-oProxy@host/repo.git")
