import json
from pathlib import Path

import pytest

from loopspec.errors import WorkflowError
from loopspec.workflow_diff import collect_diff
from loopspec.workflow_git import git
from loopspec.workflow_io import atomic_write
from tests.test_workflow_catalog import fragment_path
from tests.workflow_helpers import create_approved, home_fixture, init_repository


def execute(root: Path, *arguments: str):
    git(root, list(arguments))


def fixture(tmp_path: Path):
    init_repository(tmp_path)
    home = home_fixture(tmp_path)
    fragment_path(home, "check").write_text(
        json.dumps(
            {
                "name": "check",
                "nodes": [
                    {
                        "id": "review",
                        "gate": {
                            "outputs": {"pass": "p.md", "fail": "f.md"},
                            "evidence": {"provides": ["review"], "paths": ["**"]},
                        },
                    }
                ],
            }
        )
    )
    execute(tmp_path, "add", ".")
    execute(tmp_path, "commit", "-m", "workflow resources")
    return home


def activate(home: Path):
    return create_approved(home, [{"id": "check", "use": "check"}])


def test_dirty_before_new_and_later_commits_remain_in_fixed_diff(tmp_path: Path):
    home = fixture(tmp_path)
    (tmp_path / "initial.md").write_text("dirty before creation")
    loaded = activate(home)
    first = collect_diff(loaded)
    assert [entry["path"] for entry in first.entries] == ["initial.md"]
    execute(tmp_path, "add", "initial.md")
    execute(tmp_path, "commit", "-m", "later commit")
    assert [entry["path"] for entry in collect_diff(loaded).entries] == ["initial.md"]
    assert collect_diff(loaded).baseline == first.baseline


def test_untracked_deleted_mode_and_symlink_are_distinct_inputs(tmp_path: Path):
    home = fixture(tmp_path)
    loaded = activate(home)
    (tmp_path / "initial.md").unlink()
    path = tmp_path / "new file 中文.py"
    path.write_text("not returned as code")
    path.chmod(0o755)
    (tmp_path / "link.py").symlink_to("/outside/not-read.py")
    diff = collect_diff(loaded)
    entries = {entry["path"]: entry for entry in diff.entries}
    assert entries["initial.md"]["kind"] == "deleted"
    assert entries["new file 中文.py"]["worktree"]["mode"] == "100755"
    assert entries["link.py"]["worktree"]["mode"] == "120000"
    assert "not returned as code" not in json.dumps(entries)
    before = diff.diff_digest
    path.chmod(0o644)
    assert collect_diff(loaded).diff_digest != before


def test_staged_worktree_divergence_rejected(tmp_path: Path):
    home = fixture(tmp_path)
    loaded = activate(home)
    path = tmp_path / "initial.md"
    path.write_text("staged")
    execute(tmp_path, "add", "initial.md")
    path.write_text("different worktree")
    with pytest.raises(WorkflowError, match="暂存输入"):
        collect_diff(loaded)


def test_evidence_outputs_do_not_self_invalidate_sources_remain_visible(tmp_path: Path):
    home = fixture(tmp_path)
    loaded = activate(home)
    before = collect_diff(loaded).diff_digest
    atomic_write(loaded.root, "artifacts/check/p.md", b"report")
    atomic_write(loaded.root, ".gates/check/review/evidence.yaml", b"record")
    atomic_write(loaded.root, ".attempts/001/record.yaml", b"history")
    atomic_write(loaded.change.root, "plans/request.yaml", b"request")
    atomic_write(loaded.change.root, "state.md", b"human notes")
    assert collect_diff(loaded).diff_digest == before
    atomic_write(loaded.change.root, "artifacts/stray.md", b"not a control path")
    assert collect_diff(loaded).diff_digest != before
    (loaded.change.root / "artifacts/stray.md").unlink()
    (home / "fragments/check/fragment.yaml").write_text("modified source definition")
    assert collect_diff(loaded).diff_digest != before


def ignore(tmp_path: Path, *patterns: str) -> None:
    (tmp_path / ".gitignore").write_text("".join(item + "\n" for item in patterns))
    execute(tmp_path, "add", ".gitignore")
    execute(tmp_path, "commit", "-m", "ignore fixture")


def configure(home: Path, *patterns: str) -> None:
    (home / "config.yaml").write_text(
        "workflow:\n  excluded_paths: " + json.dumps(list(patterns)) + "\n"
    )
    execute(home.parent, "add", ".")
    execute(home.parent, "commit", "-m", "exclusion fixture")


def test_ignored_input_is_reported_as_warning_not_hidden(tmp_path: Path):
    home = fixture(tmp_path)
    ignore(tmp_path, "hidden/", "*.local")
    loaded = activate(home)
    (tmp_path / "hidden").mkdir()
    (tmp_path / "hidden/business.py").write_text("must stay visible")
    (tmp_path / "notes.local").write_text("ignored file")
    snapshot = collect_diff(loaded)
    assert snapshot.entries == []
    assert snapshot.warnings() == {
        "ignoredPaths": ["hidden/", "notes.local"],
        "ignoredTotal": 2,
    }


def test_ignored_warning_list_is_capped_and_sorted(tmp_path: Path):
    home = fixture(tmp_path)
    ignore(tmp_path, "*.tmp")
    loaded = activate(home)
    names = [f"f{index:02d}.tmp" for index in range(25)]
    for name in reversed(names):
        (tmp_path / name).write_text(name)
    warnings = collect_diff(loaded).warnings()
    assert warnings == {"ignoredPaths": names[:20], "ignoredTotal": 25}


def test_ignored_files_do_not_change_digests(tmp_path: Path):
    home = fixture(tmp_path)
    ignore(tmp_path, "*.tmp")
    loaded = activate(home)
    (tmp_path / "initial.md").write_text("reviewed change")
    before = collect_diff(loaded)
    (tmp_path / "late.tmp").write_text("ignored later")
    after = collect_diff(loaded)
    assert after.warnings() == {"ignoredPaths": ["late.tmp"], "ignoredTotal": 1}
    assert after.diff_digest == before.diff_digest
    assert after.scope_digest(["**"]) == before.scope_digest(["**"])
    assert before.warnings() is None


def test_excluded_names_match_any_component_including_file_name(tmp_path: Path):
    home = fixture(tmp_path)
    configure(home, ".DS_Store", "__pycache__", "*.log")
    ignore(tmp_path, ".DS_Store", "__pycache__/")
    loaded = activate(home)
    for path in [
        ".DS_Store",
        "a/b/.DS_Store",
        "__pycache__/x.pyc",
        "pkg/__pycache__/y.pyc",
        "a/b/x.log",
        "a.DS_Store",
        "foo__pycache__/x",
        "x.log.bak",
    ]:
        (tmp_path / path).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / path).write_text(path)
    snapshot = collect_diff(loaded)
    assert sorted(entry["path"] for entry in snapshot.entries) == [
        "a.DS_Store",
        "foo__pycache__/x",
        "x.log.bak",
    ]
    assert snapshot.warnings() is None


def test_excluded_paths_with_slash_match_the_whole_path(tmp_path: Path):
    home = fixture(tmp_path)
    configure(home, "docs/**", "loopspec/config.yaml")
    loaded = activate(home)
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs/a.md").write_text("doc")
    (tmp_path / "src/loopspec").mkdir(parents=True)
    (tmp_path / "src/loopspec/config.yaml").write_text("not excluded")
    (home / "config.yaml").write_text(
        (home / "config.yaml").read_text() + "  required_fragments: []\n"
    )
    paths = [entry["path"] for entry in collect_diff(loaded).entries]
    assert paths == ["src/loopspec/config.yaml"]


def test_ignored_path_matching_excluded_paths_is_not_warned(tmp_path: Path):
    home = fixture(tmp_path)
    configure(home, ".idea", "repos/**")
    ignore(tmp_path, ".idea/", "/repos/")
    loaded = activate(home)
    for path in [".idea/workspace.xml", "repos/clone/file.txt"]:
        (tmp_path / path).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / path).write_text(path)
    snapshot = collect_diff(loaded)
    assert snapshot.entries == []
    assert snapshot.warnings() is None


def test_home_cache_is_always_excluded_but_other_caches_are_not(tmp_path: Path):
    home = fixture(tmp_path)
    ignore(tmp_path, ".cache/", "loopspec/.cache/")
    loaded = activate(home)
    (home / ".cache/registry").mkdir(parents=True)
    (home / ".cache/registry/x").write_text("registry cache")
    (tmp_path / ".cache").mkdir()
    (tmp_path / ".cache/x").write_text("other cache")
    snapshot = collect_diff(loaded)
    assert snapshot.entries == []
    assert snapshot.warnings() == {"ignoredPaths": [".cache/"], "ignoredTotal": 1}


def test_untracked_home_cache_is_not_a_diff_entry(tmp_path: Path):
    home = fixture(tmp_path)
    loaded = activate(home)
    (home / ".cache/registry").mkdir(parents=True)
    (home / ".cache/registry/x").write_text("registry cache")
    assert collect_diff(loaded).entries == []


def test_undecodable_path_fail_closed(tmp_path: Path, monkeypatch):
    home = fixture(tmp_path)
    loaded = activate(home)
    import loopspec.workflow_diff as diff_module

    def malformed_listing(root, arguments, **kwargs):
        if arguments[:2] == ["ls-files", "--others"] and "--ignored" not in arguments:
            return b"invalid-\xff.py\0"
        return git(root, arguments, **kwargs)

    monkeypatch.setattr(diff_module, "git", malformed_listing)
    with pytest.raises(WorkflowError, match="编码"):
        collect_diff(loaded)


def test_git_output_limit_is_enforced_before_accumulation(tmp_path: Path):
    init_repository(tmp_path)
    with pytest.raises(WorkflowError, match="读取限制"):
        git(tmp_path, ["ls-tree", "-rz", "HEAD"], limit=3)


def test_rename_preserves_old_and_new_path_identity(tmp_path: Path):
    loaded = activate(fixture(tmp_path))
    (tmp_path / "initial.md").rename(tmp_path / "renamed 中文.md")
    entries = {entry["path"]: entry for entry in collect_diff(loaded).entries}
    assert entries["initial.md"]["renamed_to"] == "renamed 中文.md"
    assert entries["renamed 中文.md"]["renamed_from"] == "initial.md"


def test_concurrent_worktree_change_is_rejected(tmp_path: Path, monkeypatch):
    loaded = activate(fixture(tmp_path))
    import loopspec.workflow_diff as diff_module

    original_read = diff_module.read_bytes
    changed = False

    def changing_read(root, path, **kwargs):
        nonlocal changed
        data = original_read(root, path, **kwargs)
        if path == "initial.md" and not changed:
            changed = True
            (tmp_path / "initial.md").write_text("changed while scanning")
        return data

    monkeypatch.setattr(diff_module, "read_bytes", changing_read)
    with pytest.raises(WorkflowError, match="扫描结果不一致"):
        collect_diff(loaded)


def test_submodule_index_is_not_partially_checked(tmp_path: Path):
    loaded = activate(fixture(tmp_path))
    head = git(tmp_path, ["rev-parse", "HEAD"]).decode().strip()
    git(tmp_path, ["update-index", "--add", "--cacheinfo", "160000," + head + ",submodule"])
    with pytest.raises(WorkflowError, match="对象类型"):
        collect_diff(loaded)


def test_removed_generated_dirs_points_to_excluded_paths(tmp_path: Path):
    home = fixture(tmp_path)
    loaded = activate(home)
    (home / "config.yaml").write_text("workflow:\n  generated_dirs: [node_modules]\n")
    with pytest.raises(WorkflowError) as error:
        collect_diff(loaded)
    assert error.value.code == "config_invalid"
    assert "excluded_paths" in (error.value.fix or "")


def test_repository_identity_is_checked(tmp_path: Path):
    loaded = activate(fixture(tmp_path))
    loaded.change.state.repository = "/elsewhere"
    with pytest.raises(WorkflowError, match="仓库身份"):
        collect_diff(loaded)
