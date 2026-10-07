"""Plan lifecycle through the CLI: validate, create, show, list, approve, archive (P1–P14)."""

from pathlib import Path

import pytest
import yaml

from loopspec.workflow_git import git
from tests.workflow_helpers import (
    BUGFIX_FLOW,
    CHANGE,
    DOCS_FLOW,
    approve,
    create_approved,
    create_draft,
    fail_gate,
    home_fixture,
    invoke,
    new_change,
    node_status,
    pass_node,
    project,
    run_until,
    snapshot,
    status,
    write_request,
)


def test_validate_without_plan_is_read_only(tmp_path: Path):
    home = project(tmp_path)
    new_change(home)
    request = write_request(home, BUGFIX_FLOW, based_on="bugfix")
    before = snapshot(home)
    code, result = invoke(home, "plan", "validate", "-c", CHANGE, "-f", request)
    assert code == 0, result
    assert result["mode"] == "plan"
    assert set(result["spec"]) == {"based_on", "flow", "nodes"}
    assert len(result["digest"]) == 64
    assert snapshot(home) == before


def test_create_fixes_baseline_and_opens_plan(tmp_path: Path):
    home = project(tmp_path)
    new_change(home)
    head = git(tmp_path, ["rev-parse", "HEAD"]).decode().strip()
    result = create_draft(home, BUGFIX_FLOW)
    assert result["plan"] == "001" and result["status"] == "draft"
    state = yaml.safe_load((home / "changes" / CHANGE / ".workflow.yaml").read_text())
    assert status(home)["openPlan"] == "001" and status(home)["activePlan"] is None
    assert state["baseline"] == head
    assert state["repository"] == str(tmp_path.resolve())
    assert (home / "changes" / CHANGE / "plans/001/state.md").is_file()


def test_create_again_replaces_the_draft(tmp_path: Path):
    home = project(tmp_path)
    new_change(home)
    first = create_draft(home, BUGFIX_FLOW)
    second = create_draft(home, DOCS_FLOW)
    assert second["plan"] == "001" and second["replacedDraft"]
    assert second["digest"] != first["digest"]
    shown = invoke(home, "plan", "show", "-c", CHANGE)[1]
    assert shown["meta"]["digest"] == second["digest"]


def test_create_with_approved_plan_is_refused(tmp_path: Path):
    home = project(tmp_path)
    create_approved(home, DOCS_FLOW)
    code, result = invoke(
        home, "plan", "create", "-c", CHANGE, "-f", write_request(home, DOCS_FLOW)
    )
    assert code == 1 and result["error"] == "plan_active"
    assert "plan validate" in result["fix"] and "plan archive" in result["fix"]


def test_create_checks_project_constraints(tmp_path: Path):
    home = project(tmp_path)
    (home / "config.yaml").write_text("workflow:\n  required_fragments: [qa-testing]\n")
    new_change(home)
    code, result = invoke(
        home, "plan", "create", "-c", CHANGE, "-f", write_request(home, DOCS_FLOW)
    )
    assert code == 1 and result["error"] == "project_constraint"
    (home / "config.yaml").write_text(
        "workflow:\n  assurance_rules: fragments/change-assurance/rules.yaml\n"
    )
    code, result = invoke(
        home, "plan", "create", "-c", CHANGE, "-f", write_request(home, DOCS_FLOW)
    )
    assert code == 1 and result["error"] == "project_constraint"


def test_approve_requires_the_shown_digest(tmp_path: Path):
    home = project(tmp_path)
    new_change(home)
    draft = create_draft(home, DOCS_FLOW)
    code, result = invoke(home, "plan", "approve", "-c", CHANGE, "-p", "001", "--digest", "0" * 64)
    assert code == 1 and result["error"] == "plan_changed"
    assert status(home)["status"] == "planning"
    code, result = invoke(
        home, "plan", "approve", "-c", CHANGE, "-p", "001", "--digest", draft["digest"]
    )
    assert code == 0 and result["revision"] == 1
    assert status(home)["activePlan"] == "001"


def test_draft_replaced_after_showing_cannot_be_approved(tmp_path: Path):
    home = project(tmp_path)
    new_change(home)
    shown = create_draft(home, DOCS_FLOW)["digest"]
    create_draft(home, BUGFIX_FLOW)
    code, result = invoke(home, "plan", "approve", "-c", CHANGE, "-p", "001", "--digest", shown)
    assert code == 1 and result["error"] == "plan_changed"


def test_approve_rechecks_current_constraints(tmp_path: Path):
    home = project(tmp_path)
    new_change(home)
    draft = create_draft(home, DOCS_FLOW)
    (home / "config.yaml").write_text("workflow:\n  required_fragments: [qa-testing]\n")
    code, result = invoke(
        home, "plan", "approve", "-c", CHANGE, "-p", "001", "--digest", draft["digest"]
    )
    assert code == 1 and result["error"] == "project_constraint"
    assert status(home)["status"] == "planning"


def test_repeated_approval_is_idempotent(tmp_path: Path):
    home = project(tmp_path)
    new_change(home)
    draft = create_draft(home, DOCS_FLOW)
    approve(home, "001")
    pass_node(home, "requirements/proposal")
    code, result = invoke(
        home, "plan", "approve", "-c", CHANGE, "-p", "001", "--digest", draft["digest"]
    )
    assert code == 0 and result["alreadyApproved"] and result["revision"] == 1
    assert node_status(home, "requirements/proposal") == "done"


def test_show_and_list(tmp_path: Path):
    home = project(tmp_path)
    new_change(home)
    create_draft(home, DOCS_FLOW, args=["--note", "第一版"])
    shown = invoke(home, "plan", "show", "-c", CHANGE)[1]
    assert shown["plan"] == "001" and shown["meta"]["status"] == "draft"
    assert shown["baseline"] and shown["spec"]["nodes"]
    invoke(home, "plan", "archive", "-c", CHANGE, "-p", "001")
    create_draft(home, BUGFIX_FLOW)
    listing = invoke(home, "plan", "list", "-c", CHANGE)[1]["plans"]
    assert [(item["plan"], item["status"]) for item in listing] == [
        ("001", "archived"),
        ("002", "draft"),
    ]
    assert listing[0]["note"] == "第一版"
    old = invoke(home, "plan", "show", "-c", CHANGE, "-p", "001")[1]
    assert old["meta"]["status"] == "archived"


def test_archive_approved_plan_keeps_its_directory(tmp_path: Path):
    home = project(tmp_path)
    create_approved(home, DOCS_FLOW)
    pass_node(home, "requirements/proposal")
    plan_dir = home / "changes" / CHANGE / "plans/001"
    before = {key: value for key, value in snapshot(plan_dir).items() if key != "plan.yaml"}
    code, result = invoke(home, "plan", "archive", "-c", CHANGE, "-p", "001", "--note", "需求变化")
    assert code == 0 and result["status"] == "archived"
    after = {key: value for key, value in snapshot(plan_dir).items() if key != "plan.yaml"}
    assert after == before
    meta = yaml.safe_load((plan_dir / "plan.yaml").read_text())["meta"]
    assert meta["status"] == "archived" and meta["archive_note"] == "需求变化"
    report = status(home)
    assert report["status"] == "unplanned"
    assert report["activePlan"] is None and report["openPlan"] is None


def test_archive_draft_then_next_create_is_002(tmp_path: Path):
    home = project(tmp_path)
    new_change(home)
    create_draft(home, DOCS_FLOW)
    assert invoke(home, "plan", "archive", "-c", CHANGE, "-p", "001")[0] == 0
    assert create_draft(home, DOCS_FLOW)["plan"] == "002"


def test_replanned_plan_starts_from_empty_state_on_same_baseline(tmp_path: Path):
    home = project(tmp_path)
    create_approved(home, BUGFIX_FLOW)
    baseline = status(home)["baseline"]
    (tmp_path / "backend/code.py").write_text("changed\n")
    run_until(home, "qa/test")
    fail_gate(home, "qa/test")
    assert invoke(home, "plan", "rollback", "-c", CHANGE, "-p", "001")[0] == 0
    git(tmp_path, ["add", "."])
    git(tmp_path, ["commit", "-q", "-m", "moves HEAD"])
    invoke(home, "plan", "archive", "-c", CHANGE, "-p", "001")
    approve(home, create_draft(home, BUGFIX_FLOW)["plan"])
    report = status(home)
    assert report["plan"] == "002" and report["baseline"] == baseline
    assert node_status(home, "requirements/proposal") == "ready"
    assert all(node["status"] != "done" for node in report["nodes"])
    history = invoke(home, "change", "history", CHANGE)[1]
    assert history["plan"] == "002" and history["attempts"] == []


@pytest.mark.parametrize("draft", [False, True])
def test_execution_commands_need_an_active_plan(tmp_path: Path, draft: bool):
    home = project(tmp_path)
    new_change(home)
    if draft:
        create_draft(home, BUGFIX_FLOW)
    for args in (
        ("node", "instructions", "-c", CHANGE, "-n", "requirements/proposal"),
        ("gate", "begin", "-c", CHANGE, "-n", "be/tests/check"),
        ("gate", "record", "-c", CHANGE, "-n", "assurance/check"),
        ("plan", "rollback", "-c", CHANGE, "-p", "001"),
    ):
        code, result = invoke(home, *args)
        assert code == 1 and result["error"] == "plan_not_active", args
        assert ("plan show" if draft else "plan create") in result["fix"]


def test_rollback_of_a_non_active_plan_is_refused(tmp_path: Path):
    home = project(tmp_path)
    create_approved(home, DOCS_FLOW)
    code, result = invoke(home, "plan", "rollback", "-c", CHANGE, "-p", "002")
    assert code == 1 and result["error"] == "plan_not_active"


def test_draft_artifacts_are_never_execution_input(tmp_path: Path):
    home = project(tmp_path)
    new_change(home)
    create_draft(home, DOCS_FLOW)
    artifact = home / "changes" / CHANGE / "plans/001/artifacts/requirements/proposal.md"
    artifact.parent.mkdir(parents=True)
    artifact.write_text("手写产物")
    report = status(home)
    assert report["status"] == "planning" and not report["isComplete"]


def test_missing_config_fields_error_mentions_removed_fields(tmp_path: Path):
    home = home_fixture(tmp_path, "schema: secure-spec-driven\n")
    code, result = invoke(home, "change", "new", CHANGE)
    assert code == 1 and result["error"] == "config_invalid"
    assert "schema" in result["fix"]
