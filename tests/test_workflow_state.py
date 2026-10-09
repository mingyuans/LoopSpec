"""Change-level state (format_version 4), plan.yaml integrity and path safety."""

from pathlib import Path

import pytest
import yaml

from loopspec.errors import WorkflowError
from loopspec.workflow_state import open_change, read_plan
from tests.workflow_helpers import (
    CHANGE,
    DOCS_FLOW,
    approve,
    create_draft,
    home_fixture,
    invoke,
    new_change,
    pass_node,
    project,
    status,
)


def test_change_new_writes_format_4_with_empty_pointers(tmp_path: Path):
    home = home_fixture(tmp_path)
    new_change(home)
    state = yaml.safe_load((home / "changes" / CHANGE / ".workflow.yaml").read_text())
    assert state["format_version"] == 4
    assert set(state) == {"format_version", "change_name", "created", "baseline", "repository"}
    assert state["baseline"] is None and state["repository"] is None
    assert (home / "changes" / CHANGE / "plans").is_dir()
    assert (home / "changes" / CHANGE / "state.md").is_file()


def test_change_new_is_idempotent(tmp_path: Path):
    home = home_fixture(tmp_path)
    new_change(home)
    code, result = invoke(home, "change", "new", CHANGE)
    assert code == 0 and result["reusedChange"]


def test_derived_status_through_the_lifecycle(tmp_path: Path):
    home = project(tmp_path)
    new_change(home)
    assert status(home)["status"] == "unplanned"
    assert status(home)["isComplete"] is False
    draft = create_draft(home, DOCS_FLOW)
    assert status(home)["status"] == "planning"
    approve(home, draft["plan"])
    assert status(home)["status"] == "active"
    for identity in ("requirements/proposal", "design/design", "design/tasks"):
        pass_node(home, identity)
    report = status(home)
    assert report["status"] == "complete" and report["isComplete"]
    assert report["nextSteps"] == [f"loopspec change archive {CHANGE}"]


def test_two_open_plans_are_a_history_integrity_error(tmp_path: Path):
    home = project(tmp_path)
    new_change(home)
    create_draft(home, DOCS_FLOW)
    plans = home / "changes" / CHANGE / "plans"
    (plans / "002").mkdir()
    document = yaml.safe_load((plans / "001/plan.yaml").read_text())
    document["meta"]["plan"] = "002"
    (plans / "002/plan.yaml").write_text(yaml.safe_dump(document, sort_keys=False))
    code, result = invoke(home, "change", "status", CHANGE)
    assert code == 1 and result["error"] == "history_integrity"


def test_pointers_are_derived_from_plan_files(tmp_path: Path):
    home = project(tmp_path)
    new_change(home)
    create_draft(home, DOCS_FLOW)
    report = status(home)
    assert (report["openPlan"], report["activePlan"]) == ("001", None)
    approve(home, "001")
    report = status(home)
    assert (report["openPlan"], report["activePlan"]) == ("001", "001")


@pytest.mark.parametrize(
    "document",
    [
        "schema: secure-spec-driven\ncreated: '2026-01-01'\n",
        "format_version: 3\nchange_name: AFD1111\ncreated: '2026-01-01'\n",
    ],
)
def test_old_formats_are_unsupported(tmp_path: Path, document: str):
    home = home_fixture(tmp_path)
    root = home / "changes" / CHANGE
    root.mkdir(parents=True)
    (root / ".workflow.yaml").write_text(document)
    code, result = invoke(home, "change", "status", CHANGE)
    assert code == 1
    assert result["error"] == "unsupported_format"
    assert "v1.x" in result["fix"]


@pytest.mark.parametrize("mutation", ["nodes", "flow"])
def test_hand_edited_spec_fails_integrity(tmp_path: Path, mutation: str):
    home = project(tmp_path)
    new_change(home)
    approve(home, create_draft(home, DOCS_FLOW)["plan"])
    path = home / "changes" / CHANGE / "plans/001/plan.yaml"
    document = yaml.safe_load(path.read_text())
    if mutation == "nodes":
        document["spec"]["nodes"].pop()
    else:
        document["spec"]["flow"][0]["requires"] = ["design"]
    path.write_text(yaml.safe_dump(document, sort_keys=False))
    for args in (
        ("change", "status", CHANGE),
        ("node", "instructions", "-c", CHANGE, "-n", "requirements/proposal"),
    ):
        code, result = invoke(home, *args)
        assert code == 1 and result["error"] == "plan_integrity"


def test_plan_yaml_round_trip(tmp_path: Path):
    home = project(tmp_path)
    new_change(home)
    create_draft(home, DOCS_FLOW, args=["--note", "首次规划"])
    document = read_plan(open_change(home, CHANGE).root, "001")
    assert document.meta.status == "draft" and document.meta.revision == 0
    assert document.meta.note == "首次规划"
    raw = yaml.safe_load((home / "changes" / CHANGE / "plans/001/plan.yaml").read_text())
    assert set(raw) == {"meta", "spec"}
    assert set(raw["meta"]) == {
        "plan",
        "status",
        "revision",
        "digest",
        "approved_at",
        "note",
        "created",
        "archived_at",
        "archive_note",
    }
    assert set(raw["spec"]) == {"flow", "nodes"}


@pytest.mark.parametrize("name", ["../x", "a/b", "x;y", ".hidden", "a b"])
def test_unsafe_change_names_are_rejected(tmp_path: Path, name: str):
    home = home_fixture(tmp_path)
    code, result = invoke(home, "change", "new", name)
    assert code == 1 and result["error"] == "invalid_change_name"
    assert not any((tmp_path).glob("x*"))


@pytest.mark.parametrize("plan", ["1", "0001", "../1", "abc", "00a"])
def test_unsafe_plan_numbers_are_rejected(tmp_path: Path, plan: str):
    home = home_fixture(tmp_path)
    new_change(home)
    for args in (
        ("plan", "show", "-c", CHANGE, "-p", plan),
        ("plan", "archive", "-c", CHANGE, "-p", plan),
        ("plan", "approve", "-c", CHANGE, "-p", plan, "--digest", "x"),
    ):
        code, result = invoke(home, *args)
        assert code == 1 and result["error"] == "invalid_plan"


@pytest.mark.parametrize("path", ["../outside.yaml", "/etc/hosts", "a/../b.yaml"])
def test_request_file_must_stay_in_home(tmp_path: Path, path: str):
    home = home_fixture(tmp_path)
    (tmp_path / "outside.yaml").write_text("flow: []\n")
    new_change(home)
    code, result = invoke(home, "plan", "create", "-c", CHANGE, "-f", path)
    assert code == 1 and result["error"] == "unsafe_path"


def test_symlinked_plan_directory_is_refused(tmp_path: Path):
    home = project(tmp_path)
    new_change(home)
    create_draft(home, DOCS_FLOW)
    root = home / "changes" / CHANGE
    (root / "plans/001").rename(tmp_path / "elsewhere")
    (root / "plans/001").symlink_to(tmp_path / "elsewhere")
    code, result = invoke(home, "plan", "show", "-c", CHANGE, "-p", "001")
    assert code == 1 and result["error"] == "unsafe_path"
    with pytest.raises(WorkflowError):
        read_plan(root, "001")
