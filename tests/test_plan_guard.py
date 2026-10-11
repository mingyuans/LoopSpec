"""PreToolUse hook: LLM tools may not write an approved Plan's plan.yaml directly."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from typer.testing import CliRunner

from loopspec.cli import app
from loopspec.plan_guard import decide
from tests.workflow_helpers import BUGFIX_FLOW, create_approved, loaded, project

runner = CliRunner()

PLAN = "plans/001/plan.yaml"


def plan_text(status: str) -> str:
    meta = f"meta:\n  plan: '001'\n  status: {status}\n  revision: 1\n  digest: abc\n"
    return meta + "spec:\n  flow: []\n"


def change(tmp_path: Path, status: str = "approved", name: str = "demo") -> Path:
    """A Change root with Plan 001 in the given status; returns the Change root."""
    root = tmp_path / "loopspec" / "changes" / name
    (root / "plans" / "001").mkdir(parents=True)
    (root / ".workflow.yaml").write_text("format_version: 4\n")
    (root / PLAN).write_text(plan_text(status))
    (root / "plans" / "request.yaml").write_text("flow: []\n")
    (root / "plans" / "001" / "state.md").write_text("# Plan 001\n")
    return root


def payload(tool: str, cwd: Path, **tool_input) -> dict:
    return {
        "hook_event_name": "PreToolUse",
        "tool_name": tool,
        "tool_input": tool_input,
        "cwd": str(cwd),
    }


def bash(cwd: Path, command) -> str | None:
    return decide(payload("Bash", cwd, command=command))


# --- edit tools -----------------------------------------------------------------------------


@pytest.mark.parametrize("tool", ["Edit", "MultiEdit", "Write"])
def test_edit_tools_on_approved_plan_are_denied(tmp_path: Path, tool: str):
    root = change(tmp_path)
    inputs = {
        "Edit": {"old_string": "flow: []", "new_string": "flow: [x]"},
        "MultiEdit": {"edits": [{"old_string": "flow: []", "new_string": "flow: [x]"}]},
        "Write": {"content": plan_text("draft")},
    }[tool]
    reason = decide(payload(tool, tmp_path, file_path=str(root / PLAN), **inputs))
    assert reason is not None
    assert "plan approve" in reason and "plan archive" in reason and "001" in reason


def test_notebook_edit_on_approved_plan_is_denied(tmp_path: Path):
    root = change(tmp_path)
    assert decide(payload("NotebookEdit", tmp_path, notebook_path=str(root / PLAN), new_source="x"))


@pytest.mark.parametrize("status", ["draft", "archived"])
def test_draft_and_archived_plans_may_be_edited(tmp_path: Path, status: str):
    root = change(tmp_path, status)
    edit = {"old_string": "flow: []", "new_string": "flow: [x]"}
    assert decide(payload("Edit", tmp_path, file_path=str(root / PLAN), **edit)) is None


@pytest.mark.parametrize("name", ["plans/request.yaml", "plans/001/state.md", "state.md"])
def test_other_change_files_are_not_guarded(tmp_path: Path, name: str):
    root = change(tmp_path)
    assert decide(payload("Write", tmp_path, file_path=str(root / name), content="x")) is None


def test_relative_and_dotdot_paths_resolve_against_cwd(tmp_path: Path):
    root = change(tmp_path)
    relative = "loopspec/changes/demo/plans/../plans/001/plan.yaml"
    assert decide(payload("Edit", tmp_path, file_path=relative, old_string="a", new_string="b"))
    assert decide(
        payload("Edit", root / "plans", file_path="001/plan.yaml", old_string="a", new_string="b")
    )


def test_symlink_to_approved_plan_is_denied(tmp_path: Path):
    root = change(tmp_path)
    link = tmp_path / "alias.yaml"
    os.symlink(root / PLAN, link)
    assert decide(payload("Write", tmp_path, file_path=str(link), content="x"))


def test_plan_yaml_outside_a_change_is_ignored(tmp_path: Path):
    (tmp_path / "plans" / "001").mkdir(parents=True)
    (tmp_path / "plans" / "001" / "plan.yaml").write_text(plan_text("approved"))
    assert decide(payload("Write", tmp_path, file_path="plans/001/plan.yaml", content="x")) is None


# --- forging an approval --------------------------------------------------------------------


def test_writing_a_new_approved_plan_is_denied(tmp_path: Path):
    root = change(tmp_path)
    target = root / "plans" / "002" / "plan.yaml"
    reason = decide(
        payload("Write", tmp_path, file_path=str(target), content=plan_text("approved"))
    )
    assert reason is not None and "only loopspec plan approve" in reason


def test_editing_a_draft_into_approved_is_denied(tmp_path: Path):
    root = change(tmp_path, "draft")
    edit = {"old_string": "status: draft", "new_string": "status: approved"}
    assert decide(payload("Edit", tmp_path, file_path=str(root / PLAN), **edit))
    multi = {"edits": [{"old_string": "status: draft", "new_string": "status: approved"}]}
    assert decide(payload("MultiEdit", tmp_path, file_path=str(root / PLAN), **multi))


def test_unreadable_plan_is_let_through(tmp_path: Path):
    root = change(tmp_path)
    (root / PLAN).write_text("meta: [unclosed\n")
    edit = {"old_string": "a", "new_string": "b"}
    assert decide(payload("Edit", tmp_path, file_path=str(root / PLAN), **edit)) is None


def test_real_approved_plan_is_guarded(tmp_path: Path):
    home = project(tmp_path)
    create_approved(home, BUGFIX_FLOW)
    target = loaded(home).root / "plan.yaml"
    assert decide(payload("Write", tmp_path, file_path=str(target), content="x"))


# --- Bash -----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "command",
    [
        "sed -i '' 's/a/b/' {p}",
        "sed --in-place 's/a/b/' {p}",
        "echo x > {p}",
        "echo x >> {p}",
        "echo x | tee {p}",
        "cp /tmp/other {p}",
        "mv /tmp/other {p}",
        "rm -f {p}",
        "python3 -c \"open('{p}','w').write('x')\"",
        "dd if=/dev/null of={p}",
        "sudo env A=1 perl -pi -e 's/a/b/' {p}",
        "cat {p} && echo x > {p}",
        "echo 'unclosed > {p}",
        "sed -n 1p {p}",
        "yq -i '.meta.status = \"draft\"' {p}",
        "yq --inplace '.a = 1' {p}",
        "git diff --output={p}",
        "rg --pre ./script x {p}",
        "less -o {p} other.txt",
    ],
)
def test_bash_writes_are_denied(tmp_path: Path, command: str):
    change(tmp_path)
    assert bash(tmp_path, command.format(p="loopspec/changes/demo/" + PLAN)), command


@pytest.mark.parametrize(
    "command",
    [
        "cat {p}",
        "grep status {p}",
        "head -5 {p} | wc -l",
        "cat {p} > /tmp/copy.yaml",
        "git diff -- {p}",
        "yq '.meta.status' {p}",
        "loopspec plan show -c demo -p 001",
        "echo plan.yaml",
        "ls loopspec/changes/demo/plans/001",
    ],
)
def test_bash_reads_are_allowed(tmp_path: Path, command: str):
    change(tmp_path)
    assert bash(tmp_path, command.format(p="loopspec/changes/demo/" + PLAN)) is None, command


def test_bash_tracks_cd(tmp_path: Path):
    change(tmp_path)
    assert bash(tmp_path, "cd loopspec/changes/demo/plans/001 && sed -i '' s/a/b/ plan.yaml")
    assert bash(tmp_path, "cd loopspec/changes/demo/plans/001 && sed -n 1wplan.yaml src.txt")
    assert bash(tmp_path, "cd loopspec/changes/demo && cat plans/001/plan.yaml") is None


def test_bash_glob_reaching_approved_plan_is_denied(tmp_path: Path):
    change(tmp_path)
    assert bash(tmp_path, "sed -i '' s/a/b/ loopspec/changes/*/plans/*/plan.yaml")


def test_bash_on_draft_plan_is_allowed(tmp_path: Path):
    change(tmp_path, "draft")
    assert bash(tmp_path, "sed -i '' s/a/b/ loopspec/changes/demo/" + PLAN) is None


def test_bash_command_as_argv_list(tmp_path: Path):
    change(tmp_path)
    target = "loopspec/changes/demo/" + PLAN
    assert bash(tmp_path, ["bash", "-lc", f"echo x > {target}"])
    assert bash(tmp_path, ["cat", target]) is None


# --- Codex apply_patch ----------------------------------------------------------------------


def patch(*body: str) -> str:
    return "\n".join(["*** Begin Patch", *body, "*** End Patch"]) + "\n"


def apply_patch(cwd: Path, text: str) -> str | None:
    return decide(payload("apply_patch", cwd, command=text))


P = "loopspec/changes/demo/" + PLAN


@pytest.mark.parametrize(
    "body",
    [
        [f"*** Update File: {P}", "@@", "-  status: approved", "+  status: draft"],
        [f"*** Delete File: {P}"],
        [f"*** Add File: {P}", "+x: 1"],
        ["*** Update File: notes.md", f"*** Move to: {P}", "@@", "-a", "+b"],
        [f"*** Update File: {P}", "*** Move to: elsewhere.yaml"],
    ],
)
def test_apply_patch_touching_approved_plan_is_denied(tmp_path: Path, body: list[str]):
    change(tmp_path)
    (tmp_path / "notes.md").write_text("a\n")
    assert apply_patch(tmp_path, patch(*body))


def test_apply_patch_adding_approved_plan_is_denied(tmp_path: Path):
    change(tmp_path)
    target = "loopspec/changes/demo/plans/002/plan.yaml"
    assert apply_patch(tmp_path, patch(f"*** Add File: {target}", "+meta:", "+  status: approved"))


def test_apply_patch_on_draft_and_other_files_is_allowed(tmp_path: Path):
    change(tmp_path, "draft")
    assert (
        apply_patch(tmp_path, patch(f"*** Update File: {P}", "@@", "-flow: []", "+flow: [x]"))
        is None
    )
    assert apply_patch(tmp_path, patch("*** Add File: src/new.py", "+x = 1")) is None


def test_apply_patch_turning_draft_into_approved_is_denied(tmp_path: Path):
    change(tmp_path, "draft")
    body = [f"*** Update File: {P}", "@@", "-  status: draft", "+  status: approved"]
    assert apply_patch(tmp_path, patch(*body))


# --- the CLI entry point --------------------------------------------------------------------


def hook(stdin: str):
    return runner.invoke(app, ["hook", "pre-tool-use"], input=stdin)


def test_hook_prints_deny_decision(tmp_path: Path):
    root = change(tmp_path)
    result = hook(json.dumps(payload("Write", tmp_path, file_path=str(root / PLAN), content="x")))
    assert result.exit_code == 0
    output = json.loads(result.stdout)["hookSpecificOutput"]
    assert output["hookEventName"] == "PreToolUse"
    assert output["permissionDecision"] == "deny"
    assert "plan approve" in output["permissionDecisionReason"]


@pytest.mark.parametrize("stdin", ["", "not json", "[1, 2]", '{"tool_name": "Read"}', '{"x": 1}'])
def test_hook_allows_silently_on_irrelevant_input(stdin: str):
    result = hook(stdin)
    assert result.exit_code == 0 and result.stdout == ""


def test_hook_allows_unrelated_edit(tmp_path: Path):
    change(tmp_path)
    result = hook(json.dumps(payload("Write", tmp_path, file_path="src/x.py", content="x")))
    assert result.exit_code == 0 and result.stdout == ""


# --- deny only what is detected; anything the guard cannot check goes through ----------


def test_long_command_is_decided_quickly(tmp_path: Path):
    import time

    change(tmp_path)
    started = time.monotonic()
    command = "a" * 300_000 + " plan.yaml " + "echo x > loopspec/changes/demo/" + PLAN
    assert bash(tmp_path, command)
    assert time.monotonic() - started < 2


def test_oversized_input_is_allowed():
    from loopspec.plan_guard import hook_output

    stdin = json.dumps({"tool_name": "Bash", "tool_input": {"command": "x" * 200}})
    assert hook_output(stdin, limit=100) == ""


def test_failure_to_check_is_let_through(monkeypatch):
    import loopspec.plan_guard as guard

    def broken(payload):
        raise ValueError("boom")

    monkeypatch.setattr(guard, "decide", broken)
    assert guard.hook_output(json.dumps({"tool_name": "Bash", "tool_input": {}})) == ""


def test_time_budget_lets_slow_analysis_through(monkeypatch):
    import time

    import loopspec.plan_guard as guard

    monkeypatch.setattr(guard, "decide", lambda payload: time.sleep(5))
    started = time.monotonic()
    assert guard.hook_output(json.dumps({"tool_name": "Bash", "tool_input": {}}), budget=1) == ""
    assert time.monotonic() - started < 3


def test_deep_nesting_is_bounded_and_still_caught(tmp_path: Path):
    import shlex

    change(tmp_path)

    def nest(levels: int) -> str:
        script = "echo x > loopspec/changes/demo/" + PLAN
        for _ in range(levels):
            script = "bash -c " + shlex.quote(script)
        return "echo " + shlex.quote(script)  # `echo` reads; only the nested script writes

    assert bash(tmp_path, nest(3))
    # Past MAX_NESTING the script is not parsed, but `bash -c '<script naming the plan>'`
    # one level up is already a non-read command on it, so it is still caught, no error.
    assert bash(tmp_path, nest(12))


def test_fifo_in_plan_position_is_let_through_without_blocking(tmp_path: Path):
    root = change(tmp_path)
    (root / PLAN).unlink()
    os.mkfifo(root / PLAN)
    assert decide(payload("Write", tmp_path, file_path=str(root / PLAN), content="x")) is None


def test_glob_without_plan_yaml_text_is_denied(tmp_path: Path):
    change(tmp_path)
    assert bash(tmp_path, "sed -i '' s/a/b/ loopspec/changes/demo/plans/001/pl?n.yaml")
    assert bash(tmp_path, "cd loopspec/changes/demo/plans/001 && rm *")
    assert bash(tmp_path, "cd loopspec/changes/demo/plans/001 && cat *") is None


def test_quoted_pieces_are_joined_before_matching(tmp_path: Path):
    change(tmp_path)
    assert bash(tmp_path, "sed -i '' s/a/b/ loopspec/changes/demo/plans/001/p'l'an.yaml")
