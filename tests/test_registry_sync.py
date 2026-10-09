"""Lock file, three-way classification, `update` plans and `apply` writes (D5–D7, D10)."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
import yaml

from loopspec import registry_git
from loopspec.errors import WorkflowError
from loopspec.registry_sync import LOCK_FILE, apply, synced_versions, update
from loopspec.workflow_io import write_lock
from tests.registry_helpers import commit, make_registry, url
from tests.workflow_helpers import home_fixture

QA = "fragments/qa-testing/test.instruction.md"
DESIGN = "fragments/design/design.instruction.md"
BUGFIX = "profiles/bugfix.yaml"


def setup(tmp_path: Path, *, version: str = "latest", tag: str = "v1.0.0") -> tuple[Path, Path]:
    registry = make_registry(tmp_path / "registry")
    commit(registry, "release", tag=tag)
    project = tmp_path / "project"
    project.mkdir()
    config = f"workflow: {{}}\nregistry:\n  url: {url(registry)}\n  version: {version}\n"
    return registry, home_fixture(project, config)


def snapshot(home: Path) -> dict[str, bytes]:
    return {
        str(p.relative_to(home)): p.read_bytes()
        for kind in ("fragments", "profiles")
        for p in sorted((home / kind).rglob("*"))
        if p.is_file()
    }


def statuses(result: dict) -> dict[str, str]:
    return {item["path"]: item["status"] for item in result["files"]}


def entry(result: dict, path: str) -> dict:
    return next(item for item in result["files"] if item["path"] == path)


def lock(home: Path) -> dict:
    return yaml.safe_load((home / LOCK_FILE).read_text())


def synced(tmp_path: Path, **options: str) -> tuple[Path, Path]:
    """A project already synced to the registry's first release."""
    registry, home = setup(tmp_path, **options)
    apply(home, update(home)["planId"], [], [])
    return registry, home


def add_fragment(registry: Path, name: str) -> None:
    source = registry / "fragments" / "requirements"
    target = registry / "fragments" / name
    shutil.copytree(source, target)
    definition = target / "fragment.yaml"
    definition.write_text(definition.read_text().replace("name: requirements", f"name: {name}"))


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
    home = home_fixture(tmp_path)
    for action in (lambda: update(home), lambda: apply(home, "0" * 64, [], [])):
        with pytest.raises(WorkflowError) as caught:
            action()
        assert caught.value.code == "registry_not_configured"


def test_first_sync_classifies_without_writing(tmp_path: Path) -> None:
    registry, home = setup(tmp_path)
    (home / QA).write_text("project specific\n")
    add_fragment(registry, "extra")
    commit(registry, "extra", tag="v1.1.0")
    before = snapshot(home)
    result = update(home)
    found = statuses(result)
    assert found[QA] == "conflict"
    assert found["fragments/extra/fragment.yaml"] == "upstream-added"
    assert DESIGN not in found  # unchanged entries are not listed
    assert result["upToDate"] is False
    assert result["upstreamTag"] == "v1.1.0"
    assert result["baseCommit"] is None and result["baseTag"] is None
    assert snapshot(home) == before
    assert not (home / LOCK_FILE).exists()
    assert (home / ".cache" / "registry" / ".gitignore").read_text() == "*\n"
    item = entry(result, QA)
    assert Path(item["upstreamPath"]).resolve().is_relative_to(home.resolve())
    assert Path(item["upstreamPath"]).read_bytes() == (registry / QA).read_bytes()
    assert item["basePath"] is None
    assert Path(item["localPath"]) == (home / QA).absolute()
    extra = next(d for d in result["definitions"] if d["name"] == "extra")
    assert extra == {
        "kind": "fragment",
        "name": "extra",
        "deletedUpstream": False,
        "baseTag": None,
        "baseCommit": None,
        "upstreamTag": "v1.1.0",
        "upstreamCommit": result["upstreamCommit"],
    }


def test_categories_after_sync(tmp_path: Path) -> None:
    registry, home = synced(tmp_path)
    (registry / DESIGN).write_text("upstream change\n")
    (home / QA).write_text("local change\n")
    (registry / BUGFIX).write_text((registry / BUGFIX).read_text() + "# upstream\n")
    (home / BUGFIX).write_text((home / BUGFIX).read_text() + "# local\n")
    (registry / "fragments" / "design" / "tasks.template.md").unlink()
    (home / "fragments" / "design" / "tasks.instruction.md").unlink()
    (home / "fragments" / "design" / "notes.md").write_text("mine")
    commit(registry, "v2", tag="v2.0.0")
    result = update(home)
    assert statuses(result) == {
        DESIGN: "upstream-modified",
        QA: "local-modified",
        BUGFIX: "conflict",
        "fragments/design/tasks.template.md": "upstream-deleted",
        "fragments/design/tasks.instruction.md": "local-deleted",
        "fragments/design/notes.md": "local-only",
    }
    assert result["baseTag"] == "v1.0.0" and result["baseAvailable"] is True
    item = entry(result, BUGFIX)
    base = Path(item["basePath"]).read_text()
    assert "# upstream" not in base and "# local" not in base
    design = next(d for d in result["definitions"] if d["name"] == "design")
    assert (design["baseTag"], design["upstreamTag"]) == ("v1.0.0", "v2.0.0")


def test_upstream_deleted_definition(tmp_path: Path) -> None:
    registry, home = synced(tmp_path)
    shutil.rmtree(registry / "fragments" / "frontend-tests")
    commit(registry, "drop", tag="v2.0.0")
    result = update(home)
    gone = next(d for d in result["definitions"] if d["name"] == "frontend-tests")
    assert gone["deletedUpstream"] is True and gone["upstreamTag"] is None
    assert statuses(result)["fragments/frontend-tests/fragment.yaml"] == "upstream-deleted"


def test_local_symlink_is_unsupported(tmp_path: Path) -> None:
    registry, home = synced(tmp_path)
    (home / QA).unlink()
    (home / QA).symlink_to(home / DESIGN)
    (registry / QA).write_text("changed\n")
    commit(registry, "v2", tag="v2.0.0")
    result = update(home)
    assert QA in result["unsupported"]
    assert QA not in statuses(result)


def test_unchanged_commit_only_runs_ls_remote(tmp_path: Path, git_calls: list[str]) -> None:
    _, home = synced(tmp_path)
    git_calls.clear()
    result = update(home)
    assert result["upToDate"] is True and result["planId"] is None
    # A fresh private repository is created each time; nothing is fetched or read.
    assert git_calls == ["init", "ls-remote"]


def test_pinned_and_synced_is_offline(tmp_path: Path, git_calls: list[str]) -> None:
    _, home = synced(tmp_path, version="v1.0.0")
    git_calls.clear()
    assert update(home)["upToDate"] is True
    assert git_calls == []


def test_full_always_fetches(tmp_path: Path, git_calls: list[str]) -> None:
    _, home = synced(tmp_path, version="v1.0.0")
    git_calls.clear()
    result = update(home, full=True)
    assert result["upToDate"] is False and result["files"] == []
    assert "fetch" in git_calls


def test_skipped_definition_reappears_without_new_commit(tmp_path: Path) -> None:
    registry, home = synced(tmp_path)
    (registry / DESIGN).write_text("upstream change\n")
    commit(registry, "v2", tag="v2.0.0")
    apply(home, update(home)["planId"], [], [DESIGN])
    result = update(home)
    assert result["upToDate"] is False
    assert statuses(result) == {DESIGN: "upstream-modified"}


def test_invalid_lock_is_config_invalid(tmp_path: Path) -> None:
    _, home = synced(tmp_path)
    (home / LOCK_FILE).write_text("version: 1\ncommit: nothex\n")
    with pytest.raises(WorkflowError) as caught:
        update(home)
    assert caught.value.code == "config_invalid"


# ---------------------------------------------------------------------- apply


def test_first_apply_writes_lock(tmp_path: Path) -> None:
    registry, home = setup(tmp_path)
    result = update(home)
    applied = apply(home, result["planId"], [], [])
    assert applied["upstreamTag"] == "v1.0.0"
    data = lock(home)
    assert data["tag"] == "v1.0.0" and data["commit"] == result["upstreamCommit"]
    assert data["registry"]["url"] == url(registry)
    assert data["definitions"]["fragments/design"] == {
        "tag": "v1.0.0",
        "commit": result["upstreamCommit"],
    }
    assert set(data["files"]) >= {QA, DESIGN, BUGFIX}
    assert not (home / ".cache" / "registry" / "plan.json").exists()
    assert not (home / ".cache" / "registry" / "staging").exists()


def test_apply_writes_upstream_changes(tmp_path: Path) -> None:
    registry, home = synced(tmp_path)
    (registry / DESIGN).write_text("upstream change\n")
    (registry / "fragments" / "design" / "tasks.template.md").unlink()
    add_fragment(registry, "extra")
    # tasks.template.md is referenced by fragment.yaml, so drop the reference too.
    definition = registry / "fragments" / "design" / "fragment.yaml"
    text = definition.read_text()
    definition.write_text(text.replace("  template: tasks.template.md\n", ""))
    assert definition.read_text() != text
    commit(registry, "v2.0.1", tag="v2.0.1")
    result = update(home)
    applied = apply(home, result["planId"], [], [])
    assert (home / DESIGN).read_text() == "upstream change\n"
    assert not (home / "fragments" / "design" / "tasks.template.md").exists()
    assert (home / "fragments" / "extra" / "fragment.yaml").is_file()
    assert DESIGN in applied["written"]
    assert "fragments/design/tasks.template.md" in applied["deleted"]
    assert lock(home)["tag"] == "v2.0.1"


def test_apply_deletes_whole_definition_and_empty_dirs(tmp_path: Path) -> None:
    registry, home = synced(tmp_path)
    add_fragment(registry, "extra")
    commit(registry, "extra", tag="v1.1.0")
    apply(home, update(home)["planId"], [], [])
    assert "fragments/extra" in lock(home)["definitions"]
    shutil.rmtree(registry / "fragments" / "extra")
    commit(registry, "drop", tag="v2.0.0")
    apply(home, update(home)["planId"], [], [])
    assert not (home / "fragments" / "extra").exists()
    assert "fragments/extra" not in lock(home)["definitions"]


def test_deleting_a_used_fragment_fails_validation(tmp_path: Path) -> None:
    registry, home = synced(tmp_path)
    shutil.rmtree(registry / "fragments" / "frontend-tests")
    commit(registry, "drop", tag="v2.0.0")
    with pytest.raises(WorkflowError) as caught:
        apply(home, update(home)["planId"], [], [])
    assert "frontend-implementation" in caught.value.message
    assert (home / "fragments" / "frontend-tests" / "fragment.yaml").is_file()


def test_stale_plan_id(tmp_path: Path) -> None:
    _, home = setup(tmp_path)
    update(home)
    with pytest.raises(WorkflowError) as caught:
        apply(home, "0" * 64, [], [])
    assert caught.value.code == "registry_plan_stale"


def test_unresolved_conflict(tmp_path: Path) -> None:
    _, home = setup(tmp_path)
    (home / QA).write_text("mine\n")
    plan = update(home)["planId"]
    with pytest.raises(WorkflowError) as caught:
        apply(home, plan, [], [])
    assert caught.value.code == "registry_conflict_unresolved"


@pytest.mark.parametrize(
    ("resolves", "skips"),
    [
        ([f"{DESIGN}=local"], []),  # not a conflict
        ([f"{QA}=theirs"], []),  # unknown choice
        ([f"{QA}=local", f"{QA}=upstream"], []),  # duplicate
        ([f"{QA}=local"], [DESIGN]),  # skip of an unchanged entry
        ([f"{QA}=local"], [QA]),  # conflicts are resolved, not skipped
        ([f"../{QA}=local"], []),
    ],
)
def test_invalid_resolutions(tmp_path: Path, resolves: list[str], skips: list[str]) -> None:
    _, home = setup(tmp_path)
    (home / QA).write_text("mine\n")
    plan = update(home)["planId"]
    with pytest.raises(WorkflowError) as caught:
        apply(home, plan, resolves, skips)
    assert caught.value.code in {"config_invalid", "unsafe_path"}


@pytest.mark.parametrize("choice", ["local", "upstream"])
def test_resolve_choices(tmp_path: Path, choice: str) -> None:
    registry, home = setup(tmp_path)
    (home / QA).write_text("mine\n")
    plan = update(home)["planId"]
    if choice == "local":
        (home / QA).write_text("merged\n")  # the agent's confirmed merge
    apply(home, plan, [f"{QA}=local" if choice == "local" else f"{QA}=upstream"], [])
    expected = "merged\n" if choice == "local" else (registry / QA).read_text()
    assert (home / QA).read_text() == expected
    assert update(home)["upToDate"] is True


def test_local_drift_after_plan_is_stale(tmp_path: Path) -> None:
    registry, home = synced(tmp_path)
    (registry / DESIGN).write_text("upstream change\n")
    commit(registry, "v2", tag="v2.0.0")
    plan = update(home)["planId"]
    (home / DESIGN).write_text("edited after the plan\n")
    with pytest.raises(WorkflowError) as caught:
        apply(home, plan, [], [])
    assert caught.value.code == "registry_plan_stale"
    assert (home / DESIGN).read_text() == "edited after the plan\n"


def test_tampered_staging_is_stale(tmp_path: Path) -> None:
    registry, home = synced(tmp_path)
    (registry / DESIGN).write_text("upstream change\n")
    commit(registry, "v2", tag="v2.0.0")
    result = update(home)
    Path(entry(result, DESIGN)["upstreamPath"]).write_text("tampered\n")
    with pytest.raises(WorkflowError) as caught:
        apply(home, result["planId"], [], [])
    assert caught.value.code == "registry_plan_stale"


@pytest.mark.parametrize("broken", ["fragment", "profile"])
def test_invalid_result_writes_nothing(tmp_path: Path, broken: str) -> None:
    registry, home = synced(tmp_path)
    (registry / DESIGN).write_text("upstream change\n")
    if broken == "fragment":
        (registry / "fragments" / "design" / "fragment.yaml").write_text("name: [oops\n")
    else:
        (registry / BUGFIX).write_text(
            (registry / BUGFIX).read_text().replace("use: qa-testing", "use: no-such-fragment")
        )
    commit(registry, "broken", tag="v2.0.0")
    before, lock_before = snapshot(home), (home / LOCK_FILE).read_bytes()
    with pytest.raises(WorkflowError):
        apply(home, update(home)["planId"], [], [])
    assert snapshot(home) == before
    assert (home / LOCK_FILE).read_bytes() == lock_before


def test_skip_keeps_old_base_and_version(tmp_path: Path) -> None:
    registry, home = synced(tmp_path)
    first = lock(home)
    (registry / DESIGN).write_text("upstream change\n")
    (registry / QA).write_text("qa change\n")
    commit(registry, "v2", tag="v2.0.0")
    apply(home, update(home)["planId"], [], [DESIGN])
    data = lock(home)
    assert data["files"][DESIGN] == first["files"][DESIGN]
    assert data["definitions"]["fragments/design"] == first["definitions"]["fragments/design"]
    assert data["definitions"]["fragments/qa-testing"]["tag"] == "v2.0.0"
    assert data["tag"] == "v2.0.0"
    versions = synced_versions(home)
    assert versions["fragments/design"]["syncedTag"] == "v1.0.0"
    assert versions["fragments/qa-testing"]["syncedTag"] == "v2.0.0"


def test_concurrent_apply_is_rejected(tmp_path: Path) -> None:
    _, home = setup(tmp_path)
    plan = update(home)["planId"]
    with write_lock(home / ".cache" / "registry"):
        with pytest.raises(WorkflowError) as caught:
            apply(home, plan, [], [])
    assert caught.value.code == "concurrent_write"


def test_synced_versions_tolerates_broken_lock(tmp_path: Path) -> None:
    _, home = synced(tmp_path)
    (home / LOCK_FILE).write_text(":::")
    assert synced_versions(home) == {}
    (tmp_path / "other").mkdir()
    assert synced_versions(home_fixture(tmp_path / "other")) == {}


def test_relative_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _, home = setup(tmp_path)
    monkeypatch.chdir(home.parent)
    relative = Path(home.name)
    result = update(relative)
    apply(relative, result["planId"], [], [])
    assert update(relative)["upToDate"] is True


def test_local_files_with_unsafe_names_are_ignored(tmp_path: Path) -> None:
    registry, home = synced(tmp_path)
    (home / "fragments" / "design" / "$(id).md").write_text("x")
    (registry / DESIGN).write_text("upstream change\n")
    commit(registry, "v2", tag="v2.0.0")
    result = update(home)
    assert not any("$(" in item["path"] for item in result["files"])
    assert not any("$(" in path for path in result["unsupported"])
    assert any("名称不合法" in warning for warning in result["warnings"])


def test_lock_with_unsafe_file_name_is_invalid(tmp_path: Path) -> None:
    _, home = synced(tmp_path)
    data = lock(home)
    data["files"]["fragments/design/$(id).md"] = "0" * 64
    (home / LOCK_FILE).write_text(yaml.safe_dump(data))
    with pytest.raises(WorkflowError) as caught:
        update(home)
    assert caught.value.code == "config_invalid"


def test_forged_plan_cannot_write_outside_definitions(tmp_path: Path) -> None:
    import hashlib
    import json

    from loopspec.workflow_io import digest

    registry, home = synced(tmp_path)
    (registry / DESIGN).write_text("upstream change\n")
    commit(registry, "v2", tag="v2.0.0")
    update(home)
    plan_path = home / ".cache" / "registry" / "plan.json"
    plan = json.loads(plan_path.read_text())
    payload = b"forged"
    plan["entries"].append(
        {
            "path": "changes/x/evidence.md",
            "status": "upstream-added",
            "base": None,
            "local": None,
            "upstream": hashlib.sha256(payload).hexdigest(),
        }
    )
    body = {k: v for k, v in plan.items() if k != "plan_id"}
    plan["plan_id"] = digest(body)
    staged = home / ".cache" / "registry" / "staging" / plan["plan_id"] / "upstream"
    (staged / "changes" / "x").mkdir(parents=True)
    (staged / "changes" / "x" / "evidence.md").write_bytes(payload)
    plan_path.write_text(json.dumps(plan))
    with pytest.raises(WorkflowError):
        apply(home, plan["plan_id"], [], [])
    assert not (home / "changes" / "x" / "evidence.md").exists()
    assert (home / DESIGN).read_text() != "upstream change\n"


# ------------------------------------------------- code review regressions


@pytest.mark.parametrize("version", ["latest", "v1.1.0"])
def test_skipped_new_definition_is_not_forgotten(tmp_path: Path, version: str) -> None:
    registry, home = synced(tmp_path)
    add_fragment(registry, "extra")
    commit(registry, "extra", tag="v1.1.0")
    config = home / "config.yaml"
    config.write_text(config.read_text().replace("version: latest", f"version: {version}"))
    result = update(home)
    added = [i["path"] for i in result["files"] if i["status"] == "upstream-added"]
    assert added
    apply(home, result["planId"], [], added)
    assert lock(home)["held"] == ["fragments/extra"]
    again = update(home)
    assert again["upToDate"] is False
    assert {i["path"] for i in again["files"]} == set(added)
    apply(home, again["planId"], [], [])
    assert lock(home)["held"] == []
    assert lock(home)["definitions"]["fragments/extra"]["tag"] == "v1.1.0"
    assert update(home)["upToDate"] is True


def test_deleting_a_fragment_used_by_a_local_profile_fails(tmp_path: Path) -> None:
    registry, home = synced(tmp_path)
    add_fragment(registry, "extra")
    commit(registry, "extra", tag="v1.1.0")
    apply(home, update(home)["planId"], [], [])
    (home / "profiles" / "mine.yaml").write_text(
        "version: 1\nname: mine\nflow:\n- id: extra\n  use: extra\n"
    )
    shutil.rmtree(registry / "fragments" / "extra")
    commit(registry, "drop", tag="v2.0.0")
    with pytest.raises(WorkflowError) as caught:
        apply(home, update(home)["planId"], [], [])
    assert "profiles/mine" in caught.value.message
    assert (home / "fragments" / "extra" / "fragment.yaml").is_file()


def test_preexisting_broken_local_definition_does_not_block(tmp_path: Path) -> None:
    registry, home = synced(tmp_path)
    (home / "profiles" / "broken.yaml").write_text("version: 1\nname: broken\nflow: []\n")
    (registry / DESIGN).write_text("upstream change\n")
    commit(registry, "v2", tag="v2.0.0")
    apply(home, update(home)["planId"], [], [])
    assert (home / DESIGN).read_text() == "upstream change\n"


def test_changed_source_never_plans_deletions(tmp_path: Path) -> None:
    _, home = synced(tmp_path)
    other = make_registry(tmp_path / "other")
    shutil.rmtree(other / "fragments" / "frontend-tests")
    (other / DESIGN).write_text("other registry\n")
    commit(other, "other", tag="v5.0.0")
    config = home / "config.yaml"
    text = config.read_text()
    config.write_text(text.replace(url(tmp_path / "registry"), url(other)))
    result = update(home)
    found = statuses(result)
    assert "upstream-deleted" not in found.values()
    assert found[DESIGN] == "conflict"
    assert found["fragments/frontend-tests/fragment.yaml"] == "local-only"
    assert result["baseAvailable"] is False
    assert any("来源" in w for w in result["warnings"])
    data = lock(home)
    assert data["registry"]["url"] == url(tmp_path / "registry")  # untouched until apply


def test_switching_between_pinned_and_latest(tmp_path: Path, git_calls: list[str]) -> None:
    registry, home = synced(tmp_path, version="v1.0.0")
    (registry / DESIGN).write_text("upstream change\n")
    commit(registry, "v2", tag="v2.0.0")
    config = home / "config.yaml"
    assert update(home)["upToDate"] is True  # pinned: offline, no newer version
    config.write_text(config.read_text().replace("version: v1.0.0", "version: latest"))
    result = update(home)
    assert result["upstreamTag"] == "v2.0.0" and statuses(result) == {DESIGN: "upstream-modified"}
    apply(home, result["planId"], [], [])
    config.write_text(config.read_text().replace("version: latest", "version: v1.0.0"))
    git_calls.clear()
    back = update(home)
    assert "ls-remote" in git_calls  # the lock is at v2.0.0, so the pin is re-resolved
    assert back["upstreamTag"] == "v1.0.0" and statuses(back) == {DESIGN: "upstream-modified"}


def test_conflict_kept_local_still_advances_definition(tmp_path: Path) -> None:
    registry, home = synced(tmp_path)
    (registry / BUGFIX).write_text((registry / BUGFIX).read_text() + "# upstream\n")
    (home / BUGFIX).write_text((home / BUGFIX).read_text() + "# local\n")
    commit(registry, "v2", tag="v2.0.0")
    apply(home, update(home)["planId"], [f"{BUGFIX}=local"], [])
    assert lock(home)["definitions"]["profiles/bugfix"]["tag"] == "v2.0.0"
    assert statuses(update(home, full=True)) == {BUGFIX: "local-modified"}
