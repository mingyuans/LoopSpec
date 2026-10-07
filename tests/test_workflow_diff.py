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


def test_ignored_business_input_is_not_silently_hidden(tmp_path: Path):
    home = fixture(tmp_path)
    (tmp_path / ".gitignore").write_text("hidden/\n")
    execute(tmp_path, "add", ".gitignore")
    execute(tmp_path, "commit", "-m", "ignore fixture")
    loaded = activate(home)
    (tmp_path / "hidden").mkdir()
    (tmp_path / "hidden/business.py").write_text("must not disappear")
    with pytest.raises(WorkflowError, match="忽略文件"):
        collect_diff(loaded)


def test_supported_generated_directory_exclusion_is_read_from_config(tmp_path: Path):
    home = fixture(tmp_path)
    (home / "config.yaml").write_text("workflow:\n  generated_dirs: [node_modules]\n")
    (tmp_path / ".gitignore").write_text("node_modules/\n")
    execute(tmp_path, "add", ".")
    execute(tmp_path, "commit", "-m", "allow generated directory")
    loaded = activate(home)
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules/generated.js").write_text("generated")
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


def test_business_directory_cannot_be_declared_generated(tmp_path: Path):
    home = fixture(tmp_path)
    loaded = activate(home)
    (home / "config.yaml").write_text("workflow:\n  generated_dirs: [src]\n")
    with pytest.raises(WorkflowError, match="业务目录"):
        collect_diff(loaded)


def test_repository_identity_is_checked(tmp_path: Path):
    loaded = activate(fixture(tmp_path))
    loaded.change.state.repository = "/elsewhere"
    with pytest.raises(WorkflowError, match="仓库身份"):
        collect_diff(loaded)
