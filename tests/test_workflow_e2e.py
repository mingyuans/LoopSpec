"""Whole flows through the real CLI inside an isolated Git repository (E1–E4)."""

from datetime import date
from pathlib import Path

import pytest
import yaml

from loopspec.builtin_resources import builtin_root
from loopspec.workflow_git import git
from tests.workflow_helpers import (
    BUGFIX_FLOW,
    CHANGE,
    approve,
    create_approved,
    create_draft,
    fail_gate,
    invoke,
    new_change,
    node_status,
    pass_node,
    project,
    run_until,
    status,
    write_request,
)


def profile_flow(name: str) -> list[dict]:
    return yaml.safe_load((builtin_root() / f"profiles/{name}.yaml").read_text())["flow"]


def finish(home: Path) -> dict:
    for _ in range(64):
        report = status(home)
        if report["isComplete"]:
            return report
        ready = next(node["id"] for node in report["nodes"] if node["status"] == "ready")
        pass_node(home, ready)
    raise AssertionError("未完成")


def test_initial_plan_rework_assurance_and_archive(tmp_path: Path):
    home = project(tmp_path)
    new_change(home)
    request = write_request(home, BUGFIX_FLOW, based_on="bugfix")
    code, preview = invoke(home, "plan", "validate", "-c", CHANGE, "-f", request)
    assert code == 0, preview
    code, draft = invoke(home, "plan", "create", "-c", CHANGE, "-f", request, "--note", "越权缺陷")
    assert code == 0 and draft["digest"] == preview["digest"]
    shown = invoke(home, "plan", "show", "-c", CHANGE, "-p", "001")[1]
    assert shown["baseline"] and shown["meta"]["digest"] == draft["digest"]
    approve(home, "001")
    (tmp_path / "backend/code.py").write_text("simulated implementation\n")
    run_until(home, "qa/test")
    fail_gate(home, "qa/test")
    assert status(home)["nextSteps"] == [f"loopspec plan rollback -c {CHANGE} -p 001"]
    code, result = invoke(home, "plan", "rollback", "-c", CHANGE, "-p", "001")
    assert code == 0, result
    assert (tmp_path / "backend/code.py").read_text() == "simulated implementation\n"
    (tmp_path / "backend/code.py").write_text("simulated bug fix\n")
    assert invoke(home, "gate", "begin", "-c", CHANGE, "-n", "be/security/check")[0] == 1
    report = finish(home)
    assert report["status"] == "complete"
    plan_dir = home / "changes" / CHANGE / "plans/001"
    for identity in ("be/tests/check", "be/security/check", "be/review/check"):
        evidence = yaml.safe_load((plan_dir / f".gates/{identity}/evidence.yaml").read_text())
        assert evidence["round"] == 2
    (tmp_path / "backend/code.py").write_text("unreviewed later edit\n")
    assert not status(home)["isComplete"]
    assert invoke(home, "change", "archive", CHANGE, "--dry-run")[0] == 1
    (tmp_path / "backend/code.py").write_text("simulated bug fix\n")
    code, result = invoke(home, "change", "archive", CHANGE)
    assert code == 0 and result["complete"], result
    assert (home / f"archive/{date.today():%Y-%m}" / CHANGE).is_dir()


def test_revision_adds_backend_after_assurance_reports_it_missing(tmp_path: Path):
    home = project(tmp_path)
    flow = profile_flow("frontend-small-change")
    create_approved(home, flow)
    (tmp_path / "frontend/code.py").write_text("frontend work\n")
    (tmp_path / "backend/code.py").write_text("backend touched too\n")
    run_until(home, "assurance/check")
    code, result = invoke(home, "gate", "record", "-c", CHANGE, "-n", "assurance/check")
    assert code == 0 and result["verdict"] == "FAIL"
    assert {name for item in result["missing_fragments"] for name in item["fragments"]} == {
        "backend-implementation"
    }
    assert node_status(home, "assurance/check") == "exhausted"
    revised = [entry for entry in flow if entry["id"] != "assurance"]
    revised.append({"id": "be", "use": "backend-implementation", "requires": ["requirements"]})
    revised.append({"id": "assurance", "use": "change-assurance", "requires": ["qa", "be"]})
    request = write_request(home, revised, name="revision.yaml", base_revision=1)
    code, preview = invoke(home, "plan", "validate", "-c", CHANGE, "-f", request)
    assert code == 0, preview
    assert preview["addedInstances"] == ["be"] and preview["rerunNodes"] == ["assurance/check"]
    code, result = invoke(
        home,
        "plan",
        "approve",
        "-c",
        CHANGE,
        "-p",
        "001",
        "-f",
        request,
        "--digest",
        preview["digest"],
    )
    assert code == 0 and result["revision"] == 2
    assert finish(home)["status"] == "complete"
    history = invoke(home, "change", "history", CHANGE)[1]["attempts"]
    assert [item["kind"] for item in history] == ["revision"]


def test_task_change_archives_plan_and_replans_on_the_same_baseline(tmp_path: Path):
    home = project(tmp_path)
    create_approved(home, profile_flow("frontend-small-change"))
    baseline = status(home)["baseline"]
    (tmp_path / "frontend/code.py").write_text("frontend work\n")
    run_until(home, "qa/test")
    (tmp_path / "backend/code.py").write_text("real fix is in the backend\n")
    git(tmp_path, ["add", "."])
    git(tmp_path, ["commit", "-q", "-m", "work in progress"])
    code, result = invoke(home, "plan", "archive", "-c", CHANGE, "-p", "001", "--note", "改为后端")
    assert code == 0, result
    replanned = [
        {"id": "requirements", "use": "requirements"},
        {"id": "fe", "use": "frontend-implementation", "requires": ["requirements"]},
        {"id": "be", "use": "backend-implementation", "requires": ["requirements"]},
        {
            "id": "qa",
            "use": "qa-testing",
            "requires": ["fe", "be"],
            "on_fail": {"reset": ["fe", "be"]},
        },
        {"id": "assurance", "use": "change-assurance", "requires": ["qa"]},
    ]
    draft = create_draft(home, replanned, args=["--note", "前后端一起修复"])
    assert draft["plan"] == "002" and draft["baseline"] == baseline
    approve(home, "002")
    report = status(home)
    assert report["plan"] == "002"
    assert node_status(home, "fe/tests/check") == "blocked"
    assert finish(home)["status"] == "complete"
    plans = invoke(home, "plan", "list", "-c", CHANGE)[1]["plans"]
    assert [(item["plan"], item["status"]) for item in plans] == [
        ("001", "archived"),
        ("002", "approved"),
    ]


@pytest.mark.parametrize("profile", ["large-feature", "frontend-small-change", "bugfix"])
def test_builtin_profiles_complete(tmp_path: Path, profile: str):
    home = project(tmp_path)
    new_change(home)
    request = write_request(home, profile_flow(profile), based_on=profile)
    assert invoke(home, "plan", "create", "-c", CHANGE, "-f", request)[0] == 0
    approve(home, "001")
    side = "frontend" if profile == "frontend-small-change" else "backend"
    (tmp_path / side / "code.py").write_text("simulated implementation\n")
    if profile == "large-feature":
        (tmp_path / "frontend/code.py").write_text("simulated implementation\n")
    assert finish(home)["isComplete"]
