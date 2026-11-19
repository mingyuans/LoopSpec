"""`registry update` plans and `registry apply` lock writes in registry (global store) mode."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

from loopspec import registry_git, registry_store
from loopspec.errors import WorkflowError
from loopspec.registry_sync import CACHE, LOCK_FILE, PLAN_FILE, apply, update
from loopspec.workflow_io import write_lock
from tests.registry_helpers import (
    add_fragment,
    commit,
    local_fragment,
    registry_project,
    sync,
    url,
)
from tests.workflow_helpers import DOCS_FLOW, create_approved

DESIGN = "fragments/design/design.instruction.md"
BUGFIX = "profiles/bugfix.yaml"


def lock(home: Path) -> dict:
    return yaml.safe_load((home / LOCK_FILE).read_text())


def statuses(result: dict) -> dict[str, str]:
    return {item["path"]: item["status"] for item in result["files"]}


def entry(result: dict, path: str) -> dict:
    return next(item for item in result["files"] if item["path"] == path)


def untracked(home: Path) -> list[str]:
    """What `git status` would show for the project, ignoring config.yaml and the lock."""
    out = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        cwd=home.parent,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return sorted(
        line[3:]
        for line in out.splitlines()
        if not line[3:].endswith(("config.yaml", LOCK_FILE))
    )


def error_code(call) -> str:  # type: ignore[no-untyped-def]
    with pytest.raises(WorkflowError) as caught:
        call()
    return caught.value.code


@pytest.fixture
def git_calls(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    calls: list[str] = []
    original = registry_git.run_git

    def recording(arguments: list[str], **options: object) -> bytes:
        calls.append(arguments[0])
        return original(arguments, **options)  # type: ignore[arg-type]

    monkeypatch.setattr(registry_git, "run_git", recording)
    return calls


# --------------------------------------------------------------------- update


def test_not_configured(tmp_path: Path) -> None:
    from tests.workflow_helpers import home_fixture

    home = home_fixture(tmp_path)
    assert error_code(lambda: update(home)) == "registry_not_configured"
    assert error_code(lambda: apply(home, "0" * 64)) == "registry_not_configured"


def test_first_update_plans_without_touching_the_project(tmp_path: Path) -> None:
    _, home = registry_project(tmp_path)
    result = update(home)
    assert result["upToDate"] is False and result["baseCommit"] is None
    assert set(statuses(result).values()) == {"added"}
    assert entry(result, DESIGN)["basePath"] is None
    assert Path(entry(result, DESIGN)["upstreamPath"]).read_text()
    assert result["nextSteps"] == [f"loopspec registry apply --plan {result['planId']}"]
    assert not (home / LOCK_FILE).exists()
    assert untracked(home) == []
    assert (home / CACHE / ".gitignore").read_text() == "*\n"


def test_first_apply_writes_only_the_lock(tmp_path: Path) -> None:
    _, home = registry_project(tmp_path)
    plan = update(home)
    result = apply(home, plan["planId"])
    assert result["applied"] is True and DESIGN in result["added"]
    written = lock(home)
    assert written["version"] == 2 and written["tag"] == "v1.0.0"
    assert written["commit"] == plan["upstreamCommit"]
    assert sorted(p.name for p in home.iterdir()) == [".cache", "config.yaml", LOCK_FILE]
    assert not (home / PLAN_FILE).exists()


def test_latest_and_unchanged_only_runs_ls_remote(tmp_path: Path, git_calls: list[str]) -> None:
    _, home = registry_project(tmp_path)
    sync(home)
    git_calls.clear()
    assert update(home)["upToDate"] is True
    assert "fetch" not in git_calls and "ls-remote" in git_calls


def test_pinned_and_synced_is_offline(tmp_path: Path, git_calls: list[str]) -> None:
    _, home = registry_project(tmp_path, version="v1.0.0")
    sync(home)
    git_calls.clear()
    assert update(home)["upToDate"] is True
    assert git_calls == []


def test_full_always_plans(tmp_path: Path) -> None:
    _, home = registry_project(tmp_path)
    sync(home)
    result = update(home, full=True)
    assert result["upToDate"] is False and result["files"] == []
    assert apply(home, result["planId"])["applied"] is True


def test_upstream_changes_are_classified_with_reviewable_content(tmp_path: Path) -> None:
    registry, home = registry_project(tmp_path)
    sync(home)
    (registry / DESIGN).write_text("new design\n")
    (registry / BUGFIX).unlink()
    add_fragment(registry, "extra")
    commit(registry, "next", tag="v1.1.0")
    result = update(home)
    found = statuses(result)
    assert found[DESIGN] == "modified" and found[BUGFIX] == "deleted"
    assert found["fragments/extra/fragment.yaml"] == "added"
    design = entry(result, DESIGN)
    assert Path(design["upstreamPath"]).read_text() == "new design\n"
    assert Path(design["basePath"]).read_text() != "new design\n"
    assert entry(result, BUGFIX)["upstreamPath"] is None
    kinds = {(d["kind"], d["name"]): d["change"] for d in result["definitions"]}
    assert kinds[("fragment", "extra")] == "added"
    assert kinds[("fragment", "design")] == "modified"
    applied = apply(home, result["planId"])
    assert applied["modified"] == [DESIGN] and applied["deleted"] == [BUGFIX]
    assert lock(home)["tag"] == "v1.1.0" and BUGFIX not in lock(home)["files"]
    assert untracked(home) == []


def test_apply_takes_effect_for_reads(tmp_path: Path) -> None:
    from tests.workflow_helpers import invoke

    registry, home = registry_project(tmp_path)
    sync(home)
    create_approved(home, DOCS_FLOW)
    path = "fragments/requirements/proposal.instruction.md"
    (registry / path).write_text("updated instruction\n")
    commit(registry, "next", tag="v1.1.0")
    sync(home)
    code, body = invoke(
        home, "node", "instructions", "-c", "AFD1111", "-n", "requirements/proposal"
    )
    assert code == 0 and body["instruction"] == "updated instruction\n"


def test_missing_base_snapshot_is_reported(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, isolated_registry_store: Path
) -> None:
    from loopspec.workflow_git import git

    registry, home = registry_project(tmp_path)
    sync(home)
    old = lock(home)["commit"]
    # The registry rewrote history: the locked commit is gone everywhere.
    (registry / DESIGN).write_text("new design\n")
    git(registry, ["add", "-A"])
    git(registry, ["commit", "-q", "--amend", "-m", "rewritten"])
    git(registry, ["tag", "-d", "v1.0.0"])
    git(registry, ["tag", "v1.1.0"])
    git(registry, ["reflog", "expire", "--expire=now", "--all"])
    git(registry, ["gc", "-q", "--prune=now"])
    shutil.rmtree(isolated_registry_store)
    monkeypatch.setattr(registry_store, "_VERIFIED", set())
    result = update(home)
    assert result["baseAvailable"] is False and result["baseCommit"] == old
    assert entry(result, DESIGN)["basePath"] is None
    assert any("hash" in warning for warning in result["warnings"])


# ---------------------------------------------------------------------- apply


def test_stale_plan_id(tmp_path: Path) -> None:
    _, home = registry_project(tmp_path)
    update(home)
    assert error_code(lambda: apply(home, "f" * 64)) == "registry_plan_stale"


def test_no_plan_is_stale(tmp_path: Path) -> None:
    _, home = registry_project(tmp_path)
    assert error_code(lambda: apply(home, "f" * 64)) == "registry_plan_stale"


def test_lock_changed_after_plan_is_stale(tmp_path: Path) -> None:
    registry, home = registry_project(tmp_path)
    sync(home)
    (registry / DESIGN).write_text("new\n")
    commit(registry, "next", tag="v1.1.0")
    plan = update(home)
    (home / LOCK_FILE).write_text((home / LOCK_FILE).read_text() + "# edited\n")
    assert error_code(lambda: apply(home, plan["planId"])) == "registry_plan_stale"


def test_config_changed_after_plan_is_stale(tmp_path: Path) -> None:
    _, home = registry_project(tmp_path)
    plan = update(home)
    config = (home / "config.yaml").read_text().replace("version: latest", "version: v1.0.0")
    (home / "config.yaml").write_text(config)
    assert error_code(lambda: apply(home, plan["planId"])) == "registry_plan_stale"


def test_tampered_plan_is_stale(tmp_path: Path) -> None:
    _, home = registry_project(tmp_path)
    plan = update(home)
    stored = json.loads((home / PLAN_FILE).read_text())
    stored["files"][DESIGN] = "0" * 64
    (home / PLAN_FILE).write_text(json.dumps(stored))
    assert error_code(lambda: apply(home, plan["planId"])) == "registry_plan_stale"


def test_concurrent_apply_is_rejected(tmp_path: Path) -> None:
    _, home = registry_project(tmp_path)
    plan = update(home)
    with write_lock(home / CACHE):
        assert error_code(lambda: apply(home, plan["planId"])) == "concurrent_write"


def test_local_copies_conflict_until_removed(tmp_path: Path) -> None:
    _, home = registry_project(tmp_path)
    (home / "fragments" / "design").mkdir(parents=True)
    (home / "profiles").mkdir()
    (home / BUGFIX).write_text("vendored\n")
    plan = update(home)
    assert plan["localConflicts"] == ["fragments/design", BUGFIX]
    assert error_code(lambda: apply(home, plan["planId"])) == "registry_local_conflict"
    assert not (home / LOCK_FILE).exists()
    shutil.rmtree(home / "fragments" / "design")
    (home / BUGFIX).unlink()
    assert apply(home, plan["planId"])["applied"] is True


def test_registry_adding_a_name_used_locally_conflicts(tmp_path: Path) -> None:
    registry, home = registry_project(tmp_path)
    sync(home)
    local_fragment(home, "extra")
    add_fragment(registry, "extra")
    commit(registry, "next", tag="v1.1.0")
    plan = update(home)
    assert plan["localConflicts"] == ["fragments/extra"]
    before = (home / LOCK_FILE).read_bytes()
    assert error_code(lambda: apply(home, plan["planId"])) == "registry_local_conflict"
    assert (home / LOCK_FILE).read_bytes() == before


def test_deleting_a_fragment_used_by_a_registry_profile_fails(tmp_path: Path) -> None:
    registry, home = registry_project(tmp_path)
    sync(home)
    before = (home / LOCK_FILE).read_bytes()
    shutil.rmtree(registry / "fragments" / "qa-testing")
    commit(registry, "drop qa", tag="v1.1.0")
    plan = update(home)
    with pytest.raises(WorkflowError) as caught:
        apply(home, plan["planId"])
    assert "profiles/" in caught.value.message
    assert (home / LOCK_FILE).read_bytes() == before


def test_preexisting_broken_local_definition_does_not_block(tmp_path: Path) -> None:
    registry, home = registry_project(tmp_path)
    sync(home)
    (home / "profiles").mkdir()
    (home / "profiles" / "broken.yaml").write_text("version: 1\nname: broken\nflow: []\n")
    (registry / DESIGN).write_text("new\n")
    commit(registry, "next", tag="v1.1.0")
    assert apply(home, update(home)["planId"])["applied"] is True


def test_breaking_an_active_plan_is_refused(tmp_path: Path) -> None:
    registry, home = registry_project(tmp_path)
    sync(home)
    create_approved(home, DOCS_FLOW)
    before = (home / LOCK_FILE).read_bytes()
    shutil.rmtree(registry / "fragments" / "design")
    (registry / "profiles" / "large-feature.yaml").unlink()
    commit(registry, "drop design", tag="v1.1.0")
    plan = update(home)
    assert {"change": "AFD1111", "path": DESIGN} in plan["brokenReferences"]
    assert error_code(lambda: apply(home, plan["planId"])) == "registry_breaks_running_plan"
    assert (home / LOCK_FILE).read_bytes() == before


def test_required_fragment_removed_upstream_is_refused(tmp_path: Path) -> None:
    registry, home = registry_project(tmp_path)
    add_fragment(registry, "extra")
    commit(registry, "extra", tag="v1.0.1")
    config = (home / "config.yaml").read_text().replace(
        "workflow: {}", "workflow:\n  required_fragments: [extra]"
    )
    (home / "config.yaml").write_text(config)
    sync(home)
    before = (home / LOCK_FILE).read_bytes()
    shutil.rmtree(registry / "fragments" / "extra")
    commit(registry, "drop extra", tag="v1.1.0")
    plan = update(home)
    assert error_code(lambda: apply(home, plan["planId"])) == "project_constraint"
    assert (home / LOCK_FILE).read_bytes() == before


def test_v1_lock_on_the_same_commit_migrates(tmp_path: Path) -> None:
    _, home = registry_project(tmp_path)
    sync(home)
    current = lock(home)
    version = {"tag": current["tag"], "commit": current["commit"]}
    legacy = {
        **current,
        "version": 1,
        "definitions": {"fragments/design": version},
        "held": ["fragments/design"],
    }
    (home / LOCK_FILE).write_text(yaml.safe_dump(legacy))
    plan = update(home)
    assert plan["upToDate"] is False and plan["migration"] is True and plan["files"] == []
    result = apply(home, plan["planId"])
    assert result["migration"] is True
    assert lock(home) == current
    assert update(home)["upToDate"] is True


def test_source_switch_lists_old_definitions_as_deleted(tmp_path: Path) -> None:
    registry, home = registry_project(tmp_path)
    sync(home)
    other = tmp_path / "other"
    shutil.copytree(registry, other)
    shutil.rmtree(other / "fragments" / "frontend-tests")
    for name in ("frontend-small-change.yaml", "large-feature.yaml"):
        (other / "profiles" / name).unlink()
    text = (other / "fragments/frontend-implementation/fragment.yaml").read_text()
    assert "frontend-tests" in text
    shutil.rmtree(other / "fragments" / "frontend-implementation")
    commit(other, "fork", tag="v1.1.0")
    config = (home / "config.yaml").read_text().replace(url(registry), url(other))
    (home / "config.yaml").write_text(config)
    plan = update(home)
    assert statuses(plan)["fragments/frontend-tests/fragment.yaml"] == "deleted"
    assert plan["sourceChanged"] is True and plan["previousRegistry"]["url"] == url(registry)
    assert any("来源" in warning for warning in plan["warnings"])
    assert apply(home, plan["planId"])["applied"] is True
    assert lock(home)["registry"]["url"] == url(other)


def test_registry_path_option(tmp_path: Path) -> None:
    _, home = registry_project(tmp_path, path="workflows")
    sync(home)
    assert DESIGN in lock(home)["files"]
    from tests.workflow_helpers import invoke

    assert invoke(home, "fragment", "show", "design")[0] == 0


def test_invalid_lock_is_config_invalid(tmp_path: Path) -> None:
    _, home = registry_project(tmp_path)
    (home / LOCK_FILE).write_text("version: 2\nregistry: {}\n")
    assert error_code(lambda: update(home)) == "config_invalid"


def test_lock_with_unsafe_file_name_is_invalid(tmp_path: Path) -> None:
    _, home = registry_project(tmp_path)
    sync(home)
    data = lock(home)
    data["files"]["fragments/design/$(evil).md"] = "0" * 64
    (home / LOCK_FILE).write_text(yaml.safe_dump(data))
    assert error_code(lambda: update(home)) == "config_invalid"


def test_relative_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _, home = registry_project(tmp_path)
    monkeypatch.chdir(home.parent)
    assert apply(Path("loopspec"), update(Path("loopspec"))["planId"])["applied"] is True


def test_deeply_nested_plan_is_stale(tmp_path: Path) -> None:
    _, home = registry_project(tmp_path)
    plan = update(home)
    (home / PLAN_FILE).write_text("[" * 100000 + "]" * 100000)
    assert error_code(lambda: apply(home, plan["planId"])) == "registry_plan_stale"


def test_repinning_a_tag_on_the_same_commit_rewrites_the_lock(tmp_path: Path) -> None:
    from loopspec.workflow_git import git

    registry, home = registry_project(tmp_path, version="v1.0.0")
    sync(home)
    git(registry, ["tag", "v1.0.1"])
    config = (home / "config.yaml").read_text().replace("version: v1.0.0", "version: v1.0.1")
    (home / "config.yaml").write_text(config)
    plan = update(home)
    assert plan["upToDate"] is False and plan["files"] == []
    apply(home, plan["planId"])
    assert lock(home)["tag"] == "v1.0.1"
    assert update(home)["upToDate"] is True


def test_first_tag_on_the_locked_head_is_picked_up(tmp_path: Path) -> None:
    from loopspec.workflow_git import git

    registry, home = registry_project(tmp_path, tag=None)
    sync(home)
    assert lock(home)["tag"] is None
    git(registry, ["tag", "v1.0.0"])
    plan = update(home)
    assert plan["upToDate"] is False
    apply(home, plan["planId"])
    assert lock(home)["tag"] == "v1.0.0"


def test_source_switch_is_reported_even_without_file_changes(tmp_path: Path) -> None:
    registry, home = registry_project(tmp_path)
    sync(home)
    mirror = tmp_path / "mirror"
    shutil.copytree(registry, mirror)
    config = (home / "config.yaml").read_text().replace(url(registry), url(mirror))
    (home / "config.yaml").write_text(config)
    plan = update(home)
    assert plan["files"] == [] and plan["sourceChanged"] is True
    assert plan["previousRegistry"]["url"] == url(registry)
    assert apply(home, plan["planId"])["applied"] is True
    assert update(home)["sourceChanged"] is False


def test_plan_whose_lock_would_be_unreadable_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, home = registry_project(tmp_path)
    monkeypatch.setattr(registry_store, "MAX_DOCUMENT_BYTES", 512)
    assert error_code(lambda: update(home)) == "resource_limit"
    assert not (home / PLAN_FILE).exists()


def test_oversized_lock_is_config_invalid(tmp_path: Path) -> None:
    _, home = registry_project(tmp_path)
    (home / LOCK_FILE).write_text("# " + "x" * (3 * 1024 * 1024) + "\n")
    assert error_code(lambda: update(home)) == "config_invalid"
