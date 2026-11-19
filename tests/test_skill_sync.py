"""Workflow commands keep a project's loopspec skill/command files in step with the CLI."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from typer.testing import CliRunner

from loopspec import skill_sync
from loopspec.cli import app
from loopspec.scaffold import expected_files, scaffold_tools
from loopspec.workflow_diff import collect_diff
from loopspec.workflow_git import git
from tests.workflow_helpers import DOCS_FLOW, create_approved, invoke, loaded, project

runner = CliRunner()
NEW_SKILL = ".claude/skills/loopspec-new/SKILL.md"
ARCHIVE_SKILL = ".claude/skills/loopspec-archive/SKILL.md"
CONTINUE_COMMAND = ".claude/commands/lpsx/continue.md"


def configured(tmp_path: Path, *tools: str) -> Path:
    """A Git project with a workflow home and loopspec skills for `tools`, committed."""
    home = project(tmp_path, code=False)
    scaffold_tools(tmp_path, list(tools or ("claude",)))
    git(tmp_path, ["add", "-A"])
    git(tmp_path, ["commit", "-q", "-m", "skills"])
    return home


def expected(root: Path, relative: str, tool: str = "claude") -> str:
    return expected_files(root, tool)[root / relative]


def stale(root: Path) -> None:
    (root / NEW_SKILL).write_text("stale skill\n")
    (root / CONTINUE_COMMAND).write_text("stale command\n")
    (root / ARCHIVE_SKILL).unlink()


def run_status(home: Path, *extra: str):  # type: ignore[no-untyped-def]
    return runner.invoke(app, ["change", "status", "NOPE1", "--json", "--home", str(home), *extra])


def test_workflow_command_rewrites_stale_and_missing_files(tmp_path: Path) -> None:
    home = configured(tmp_path)
    stale(tmp_path)
    result = run_status(home)
    for relative in (NEW_SKILL, ARCHIVE_SKILL, CONTINUE_COMMAND):
        assert (tmp_path / relative).read_text() == expected(tmp_path, relative), relative
        assert relative in result.stderr
    assert "synced 3 skill file(s)" in result.stderr
    assert '"error": "change_not_found"' in result.stdout  # the command itself is unchanged


def test_matching_files_are_left_alone(tmp_path: Path) -> None:
    home = configured(tmp_path)
    before = {p: os.stat(tmp_path / p).st_mtime_ns for p in (NEW_SKILL, CONTINUE_COMMAND)}
    result = run_status(home)
    assert result.stderr == ""
    assert {p: os.stat(tmp_path / p).st_mtime_ns for p in before} == before


def test_explicit_home_option_also_syncs_and_reaches_the_command(tmp_path: Path) -> None:
    home = configured(tmp_path)
    stale(tmp_path)
    code, body = invoke(home, "change", "new", "SYNC1")  # explicit --home
    assert code == 0 and body["changeName"] == "SYNC1"
    assert (tmp_path / NEW_SKILL).read_text() == expected(tmp_path, NEW_SKILL)


def test_default_home_syncs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    configured(tmp_path)
    stale(tmp_path)
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["memory", "list"])
    assert result.exit_code == 0, result.output
    assert (tmp_path / NEW_SKILL).read_text() == expected(tmp_path, NEW_SKILL)


def test_unconfigured_tools_are_not_created(tmp_path: Path) -> None:
    home = configured(tmp_path, "claude")
    run_status(home)
    assert not (tmp_path / ".cursor").exists() and not (tmp_path / ".codex").exists()


def test_every_configured_tool_is_synced(tmp_path: Path) -> None:
    home = configured(tmp_path, "claude", "cursor")
    cursor_skill = ".cursor/skills/loopspec-new/SKILL.md"
    (tmp_path / cursor_skill).write_text("stale\n")
    (tmp_path / NEW_SKILL).write_text("stale\n")
    run_status(home)
    assert (tmp_path / cursor_skill).read_text() == expected(tmp_path, cursor_skill, "cursor")
    assert (tmp_path / NEW_SKILL).read_text() == expected(tmp_path, NEW_SKILL)


def test_codex_global_prompts_are_never_written(
    tmp_path: Path, isolated_codex_home: Path
) -> None:
    root = tmp_path / "project"
    root.mkdir()
    home = configured(root, "codex")  # CODEX_HOME (tmp_path/codex-home) is outside it
    prompts = list(isolated_codex_home.rglob("lpsx-*.md"))
    assert prompts  # init wrote them
    prompts[0].write_text("user-global, left alone\n")
    (root / ".codex/skills/loopspec-new/SKILL.md").write_text("stale\n")
    run_status(home)
    assert prompts[0].read_text() == "user-global, left alone\n"
    assert (root / ".codex/skills/loopspec-new/SKILL.md").read_text() == expected(
        root, ".codex/skills/loopspec-new/SKILL.md", "codex"
    )


@pytest.mark.parametrize("kind", ["file", "dir"])
def test_symlinks_are_never_followed(tmp_path: Path, kind: str) -> None:
    root = tmp_path / "p"
    root.mkdir()
    home = configured(root)
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "SKILL.md").write_text("outside\n")
    if kind == "file":
        (root / NEW_SKILL).unlink()
        os.symlink(outside / "SKILL.md", root / NEW_SKILL)
    else:
        target = root / ".claude/skills/loopspec-new"
        for child in target.iterdir():
            child.unlink()
        target.rmdir()
        os.symlink(outside, target)
    result = run_status(home)
    assert (outside / "SKILL.md").read_text() == "outside\n"
    assert "could not sync" in result.stderr and NEW_SKILL in result.stderr
    assert '"error": "change_not_found"' in result.stdout


def test_sync_failure_never_breaks_the_command(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = configured(tmp_path)

    def broken(_: Path) -> None:
        raise RuntimeError("boom")

    monkeypatch.setattr(skill_sync, "sync_project_skills", broken)
    result = run_status(home)
    assert "skill sync skipped (RuntimeError)" in result.stderr
    assert '"error": "change_not_found"' in result.stdout


def test_commands_without_home_do_not_sync(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    configured(tmp_path)
    stale(tmp_path)
    monkeypatch.chdir(tmp_path)
    assert runner.invoke(app, ["version"]).exit_code == 0
    runner.invoke(app, ["hook", "pre-tool-use"], input="{}")
    assert (tmp_path / NEW_SKILL).read_text() == "stale skill\n"


def test_missing_home_or_no_tools_does_nothing(tmp_path: Path) -> None:
    assert skill_sync.sync_project_skills(tmp_path / "nope").updated == []
    home = project(tmp_path, code=False)
    assert skill_sync.sync_project_skills(home).updated == []
    assert not (tmp_path / ".claude").exists()


# --------------------------------------------------------------------------- the Diff


def diff_paths(home: Path) -> list[str]:
    return [entry["path"] for entry in collect_diff(loaded(home)).entries]


def test_synced_files_stay_out_of_the_delivery_diff(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = configured(tmp_path)
    # The baseline holds skills from an older CLI.
    stale(tmp_path)
    git(tmp_path, ["add", "-A"])
    git(tmp_path, ["commit", "-q", "-m", "old skills"])
    create_approved(home, DOCS_FLOW)
    run_status(home)  # the sync rewrites them to this CLI's content
    assert (tmp_path / NEW_SKILL).read_text() == expected(tmp_path, NEW_SKILL)
    assert not [p for p in diff_paths(home) if p.startswith(".claude/")]
    # Control: without the exclusion the same sync shows up in the Diff.
    monkeypatch.setattr(skill_sync, "all_managed_files", lambda project: {})
    synced = [p for p in diff_paths(home) if p.startswith(".claude/")]
    assert sorted(synced) == sorted([NEW_SKILL, ARCHIVE_SKILL, CONTINUE_COMMAND])


def test_edited_or_foreign_files_are_still_reviewed(tmp_path: Path) -> None:
    home = configured(tmp_path)
    create_approved(home, DOCS_FLOW)
    (tmp_path / NEW_SKILL).write_text("hand-edited instructions\n")  # not this CLI's content
    (tmp_path / ".claude/skills/loopspec-new/extra.md").write_text("foreign file\n")
    (tmp_path / ".claude/skills/other-skill").mkdir()
    (tmp_path / ".claude/skills/other-skill/SKILL.md").write_text("not loopspec\n")
    paths = diff_paths(home)
    assert NEW_SKILL in paths
    assert ".claude/skills/loopspec-new/extra.md" in paths
    assert ".claude/skills/other-skill/SKILL.md" in paths


def test_deleted_managed_file_is_still_reviewed(tmp_path: Path) -> None:
    home = configured(tmp_path)
    create_approved(home, DOCS_FLOW)
    (tmp_path / ARCHIVE_SKILL).unlink()
    assert ARCHIVE_SKILL in diff_paths(home)


def test_committed_unreviewed_content_is_not_hidden(tmp_path: Path) -> None:
    home = configured(tmp_path)
    create_approved(home, DOCS_FLOW)
    template = (tmp_path / NEW_SKILL).read_text()
    (tmp_path / NEW_SKILL).write_text("injected instructions\n")
    git(tmp_path, ["add", NEW_SKILL])
    git(tmp_path, ["commit", "-q", "-m", "sneak"])
    (tmp_path / NEW_SKILL).write_text(template)  # working tree looks like the template again
    snapshot = collect_diff(loaded(home))
    assert NEW_SKILL in snapshot.diverged or NEW_SKILL in [e["path"] for e in snapshot.entries]


def test_staged_content_different_from_the_template_is_not_hidden(tmp_path: Path) -> None:
    home = configured(tmp_path)
    create_approved(home, DOCS_FLOW)
    template = (tmp_path / NEW_SKILL).read_text()
    (tmp_path / NEW_SKILL).write_text("staged instructions\n")
    git(tmp_path, ["add", NEW_SKILL])
    (tmp_path / NEW_SKILL).write_text(template)
    with pytest.raises(Exception) as caught:  # staged and working tree disagree
        collect_diff(loaded(home))
    assert getattr(caught.value, "code", "") == "index_worktree_mismatch"


def test_committed_sync_stays_out_of_the_diff(tmp_path: Path) -> None:
    home = configured(tmp_path)
    stale(tmp_path)
    git(tmp_path, ["add", "-A"])
    git(tmp_path, ["commit", "-q", "-m", "old skills"])
    create_approved(home, DOCS_FLOW)
    run_status(home)
    git(tmp_path, ["add", "-A", ".claude"])
    git(tmp_path, ["commit", "-q", "-m", "synced skills"])
    snapshot = collect_diff(loaded(home))
    assert not [e["path"] for e in snapshot.entries if e["path"].startswith(".claude/")]
    assert not [p for p in snapshot.diverged if p.startswith(".claude/")]
