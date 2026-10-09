"""Rollback by a Gate's own on_fail; an interrupted command leaves state before or after."""

import re
from pathlib import Path

import pytest
import yaml

import loopspec.workflow_attempts as attempts
import loopspec.workflow_plans as plans
from loopspec.errors import WorkflowError
from loopspec.workflow_io import atomic_write
from tests.workflow_helpers import (
    CHANGE,
    DOCS_FLOW,
    approve,
    create_approved,
    create_draft,
    fail_gate,
    invoke,
    loaded,
    new_change,
    node_status,
    pass_node,
    project,
    status,
    write_request,
)

QA_FLOW = [
    {"id": "requirements", "use": "requirements"},
    {"id": "notes", "use": "requirements"},
    {
        "id": "qa",
        "use": "qa-testing",
        "requires": ["requirements"],
        "on_fail": {"reset": ["requirements"], "max_retries": 1},
    },
]
ROLLBACK = ("plan", "rollback", "-c", CHANGE, "-p", "001")


def failed_qa(tmp_path: Path) -> Path:
    home = project(tmp_path, code=False)
    create_approved(home, QA_FLOW)
    for identity in ("requirements/proposal", "notes/proposal"):
        pass_node(home, identity)
    fail_gate(home, "qa/test")
    return home


def interrupt(monkeypatch, module, name: str, after: int):
    """Let `after` calls through, then fail every following call."""
    original = getattr(module, name)
    calls = {"count": 0}

    def wrapper(*args, **kwargs):
        if calls["count"] >= after:
            raise WorkflowError("test_interrupt", "模拟中断")
        calls["count"] += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(module, name, wrapper)
    return lambda: monkeypatch.setattr(module, name, original)


def plan_dir(home: Path, plan: str = "001") -> Path:
    return home / "changes" / CHANGE / "plans" / plan


def approved_count(home: Path) -> int:
    return sum(
        yaml.safe_load(path.read_text())["meta"]["status"] == "approved"
        for path in (home / "changes" / CHANGE / "plans").glob("*/plan.yaml")
    )


def normalized(home: Path) -> dict:
    """Files of the Change, with wall-clock timestamps blanked out."""
    root = home / "changes" / CHANGE
    result = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.name == ".write.lock":
            continue
        text = path.read_text()
        if path.suffix == ".yaml":
            data = yaml.safe_load(text)
            for section in (data, data.get("meta", {})):
                for key in ("created", "approved_at", "archived_at"):
                    if section.get(key):
                        section[key] = "<time>"
            text = yaml.safe_dump(data)
        elif path.name == "state.md":
            text = re.sub(r"^- \S+ · ", "- <time> · ", text, flags=re.MULTILINE)
        result[str(path.relative_to(root))] = text
    return result


def test_rollback_resets_by_the_gates_own_on_fail(tmp_path: Path):
    home = failed_qa(tmp_path)
    code, result = invoke(home, *ROLLBACK)
    assert code == 0, result
    assert result["gate"] == "qa/test"
    assert result["reset"] == ["qa/test", "requirements/proposal"]
    record = yaml.safe_load((plan_dir(home) / ".attempts/001/record.yaml").read_text())
    assert record["kind"] == "rollback" and record["files"][-1]["source"].endswith("fail.md")
    assert node_status(home, "requirements/proposal") == "ready"
    assert node_status(home, "notes/proposal") == "done"
    assert node_status(home, "qa/test") == "blocked"


def test_exhausted_or_missing_on_fail_stops_for_a_human(tmp_path: Path):
    home = failed_qa(tmp_path)
    assert invoke(home, *ROLLBACK)[0] == 0
    pass_node(home, "requirements/proposal")
    fail_gate(home, "qa/test")
    report = status(home)
    assert node_status(home, "qa/test") == "exhausted" and report["nextSteps"] == []
    code, result = invoke(home, *ROLLBACK)
    assert code == 1 and result["error"] == "retries_exhausted"


def test_no_failed_gate(tmp_path: Path):
    home = project(tmp_path, code=False)
    create_approved(home, QA_FLOW)
    code, result = invoke(home, *ROLLBACK)
    assert code == 1 and result["error"] == "no_failed_gate"


@pytest.mark.parametrize(
    "report",
    [
        "verdict: FAIL\nsummary: x\nroute_case: backend\n",
        "verdict: FAIL\n",
        "verdict: FAIL\nsummary: '  '\n",
        "nonsense",
    ],
)
def test_failure_report_must_be_strict(tmp_path: Path, report: str):
    home = project(tmp_path, code=False)
    create_approved(home, QA_FLOW)
    pass_node(home, "requirements/proposal")
    atomic_write(loaded(home).root, "artifacts/qa/test/fail.md", report.encode())
    code, result = invoke(home, "change", "status", CHANGE)
    assert code == 1 and result["error"] == "invalid_verdict"


def test_prior_attempts_are_marked_untrusted(tmp_path: Path):
    home = failed_qa(tmp_path)
    assert invoke(home, *ROLLBACK)[0] == 0
    code, result = invoke(home, "node", "instructions", "-c", CHANGE, "-n", "requirements/proposal")
    assert code == 0, result
    [prior] = result["priorAttempts"]
    assert prior["kind"] == "rollback" and prior["gate"] == "qa/test"
    assert prior["untrusted"] is True and "不可信" in result["untrustedData"]
    assert Path(prior["failureReport"]).read_text().startswith("verdict: FAIL")


INSTRUCTIONS = ("node", "instructions", "-c", CHANGE, "-n")
REVISED = [
    DOCS_FLOW[0],
    {"id": "extra", "use": "requirements"},
    {**DOCS_FLOW[1], "requires": ["requirements", "extra"]},
]


def attempt_dirs(home: Path) -> list[str]:
    root = plan_dir(home) / ".attempts"
    return sorted(p.name for p in root.iterdir()) if root.is_dir() else []


def test_create_interrupted_before_commit_stays_unplanned(tmp_path: Path, monkeypatch):
    home = project(tmp_path, code=False)
    new_change(home)
    request = write_request(home, DOCS_FLOW)
    restore = interrupt(monkeypatch, plans, "write_plan", 0)
    assert invoke(home, "plan", "create", "-c", CHANGE, "-f", request)[0] == 1
    report = status(home)
    assert report["status"] == "unplanned"
    assert any("plan create" in step for step in report["nextSteps"])
    restore()
    assert invoke(home, "plan", "create", "-c", CHANGE, "-f", request)[0] == 0
    other = tmp_path / "other"
    other.mkdir()
    home2 = project(other, code=False)
    new_change(home2)
    create_draft(home2, DOCS_FLOW)
    assert normalized(home) == normalized(home2) | {
        ".workflow.yaml": normalized(home)[".workflow.yaml"]
    }
    assert status(home)["status"] == "planning" and status(home)["openPlan"] == "001"


def test_approve_interrupted_before_commit_stays_planning(tmp_path: Path, monkeypatch):
    home = project(tmp_path, code=False)
    new_change(home)
    draft = create_draft(home, DOCS_FLOW)
    restore = interrupt(monkeypatch, plans, "write_plan", 0)
    args = ("plan", "approve", "-c", CHANGE, "-p", "001", "--digest", draft["digest"])
    assert invoke(home, *args)[0] == 1
    assert status(home)["status"] == "planning" and approved_count(home) == 0
    restore()
    code, result = invoke(home, *args)
    assert code == 0 and result["revision"] == 1
    assert status(home)["status"] == "active"


def test_archive_interrupted_before_commit_keeps_the_plan(tmp_path: Path, monkeypatch):
    home = project(tmp_path, code=False)
    create_approved(home, DOCS_FLOW)
    restore = interrupt(monkeypatch, plans, "write_plan", 0)
    assert invoke(home, "plan", "archive", "-c", CHANGE, "-p", "001")[0] == 1
    assert status(home)["status"] == "active" and approved_count(home) == 1
    restore()
    assert invoke(home, "plan", "archive", "-c", CHANGE, "-p", "001")[0] == 0
    assert status(home)["status"] == "unplanned"
    approve(home, create_draft(home, DOCS_FLOW)["plan"])
    assert approved_count(home) == 1 and status(home)["activePlan"] == "002"


def finished_docs(tmp_path: Path) -> tuple[Path, str, str]:
    home = project(tmp_path, code=False)
    create_approved(home, DOCS_FLOW)
    for identity in ("requirements/proposal", "design/design", "design/tasks"):
        pass_node(home, identity)
    request = write_request(home, REVISED, name="revision.yaml", base_revision=1)
    digest = invoke(home, "plan", "validate", "-c", CHANGE, "-f", request)[1]["digest"]
    return home, request, digest


def test_revision_interrupted_before_commit_keeps_the_old_spec(tmp_path: Path, monkeypatch):
    home, request, digest = finished_docs(tmp_path)
    restore = interrupt(monkeypatch, plans, "write_plan", 0)
    args = ("plan", "approve", "-c", CHANGE, "-p", "001", "-f", request, "--digest", digest)
    assert invoke(home, *args)[0] == 1
    report = status(home)
    assert report["status"] == "complete" and report["revision"] == 1
    assert invoke(home, "change", "history", CHANGE)[1]["attempts"] == []
    restore()
    code, result = invoke(home, *args)
    assert code == 0 and result["revision"] == 2, result
    assert attempt_dirs(home) == ["001"]
    assert [a["kind"] for a in invoke(home, "change", "history", CHANGE)[1]["attempts"]] == [
        "revision"
    ]


def test_uncommitted_revision_record_is_replaced_not_kept(tmp_path: Path, monkeypatch):
    home, request, digest = finished_docs(tmp_path)
    restore = interrupt(monkeypatch, plans, "write_plan", 0)
    args = ("plan", "approve", "-c", CHANGE, "-p", "001")
    assert invoke(home, *args, "-f", request, "--digest", digest)[0] == 1
    restore()
    other_flow = [REVISED[0], {**REVISED[1], "id": "other"}]
    other_flow.append({**DOCS_FLOW[1], "requires": ["requirements", "other"]})
    other = write_request(home, other_flow, name="other.yaml", base_revision=1)
    other_digest = invoke(home, "plan", "validate", "-c", CHANGE, "-f", other)[1]["digest"]
    assert invoke(home, *args, "-f", other, "--digest", other_digest)[0] == 0
    [record] = invoke(home, "change", "history", CHANGE)[1]["attempts"]
    assert record["targetDigest"] == other_digest and attempt_dirs(home) == ["001"]


@pytest.mark.parametrize("after", [0, 1])
def test_revision_interrupted_after_commit_is_settled_later(tmp_path, monkeypatch, after):
    home, request, digest = finished_docs(tmp_path)
    restore = interrupt(monkeypatch, attempts, "archive_file", after)
    args = ("plan", "approve", "-c", CHANGE, "-p", "001", "-f", request, "--digest", digest)
    assert invoke(home, *args)[0] == 1
    restore()
    report = status(home)
    assert report["status"] == "active" and report["revision"] == 2
    assert node_status(home, "design/design") == "blocked"
    assert report["nextSteps"] == [f"loopspec node instructions -c {CHANGE} -n extra/proposal"]
    assert invoke(home, *INSTRUCTIONS, "extra/proposal")[0] == 0
    files = plan_dir(home) / ".attempts/001/files/artifacts/design"
    assert sorted(p.name for p in files.iterdir()) == ["design.md", "tasks.md"]
    assert not (plan_dir(home) / "artifacts/design/design.md").exists()
    assert invoke(home, *args)[1]["alreadyApproved"]


@pytest.mark.parametrize("after", [0, 1])
def test_rollback_interrupted_after_commit_is_settled_without_double_counting(
    tmp_path, monkeypatch, after
):
    home = failed_qa(tmp_path)
    restore = interrupt(monkeypatch, attempts, "archive_file", after)
    assert invoke(home, *ROLLBACK)[0] == 1
    restore()
    report = status(home)
    assert report["status"] == "active" and report["pendingRollback"] is None
    assert node_status(home, "requirements/proposal") == "ready"
    assert node_status(home, "qa/test") == "blocked"
    assert report["nextSteps"] == [
        f"loopspec node instructions -c {CHANGE} -n requirements/proposal"
    ]
    code, result = invoke(home, *INSTRUCTIONS, "requirements/proposal")
    assert code == 0 and result["priorAttempts"][0]["gate"] == "qa/test"
    assert not (plan_dir(home) / "artifacts/qa/test/fail.md").exists()
    assert attempt_dirs(home) == ["001"]
    pass_node(home, "requirements/proposal")
    fail_gate(home, "qa/test")
    entry = next(n for n in status(home)["nodes"] if n["id"] == "qa/test")
    assert entry["status"] == "exhausted" and entry["gate"]["rollbacksUsed"] == 1


def test_rollback_interrupted_before_commit_stays_failed(tmp_path: Path, monkeypatch):
    home = failed_qa(tmp_path)
    restore = interrupt(monkeypatch, attempts, "write_yaml", 0)
    assert invoke(home, *ROLLBACK)[0] == 1
    restore()
    assert node_status(home, "qa/test") == "failed"
    assert status(home)["nextSteps"] == [f"loopspec plan rollback -c {CHANGE} -p 001"]
    assert invoke(home, *ROLLBACK)[0] == 0
    assert attempt_dirs(home) == ["001"]


def test_tampered_archive_target_is_a_history_integrity_error(tmp_path: Path, monkeypatch):
    home = failed_qa(tmp_path)
    restore = interrupt(monkeypatch, attempts, "archive_file", 1)
    assert invoke(home, *ROLLBACK)[0] == 1
    restore()
    moved = plan_dir(home) / ".attempts/001/files/artifacts/requirements/proposal.md"
    moved.write_text("篡改")
    code, result = invoke(home, *INSTRUCTIONS, "requirements/proposal")
    assert code == 1 and result["error"] == "history_integrity"
    assert (plan_dir(home) / "artifacts/qa/test/fail.md").is_file()


@pytest.mark.parametrize("source", ["plan.yaml", "state.md", "artifacts/notes/proposal.md"])
def test_record_listing_paths_outside_the_reset_is_refused(tmp_path, monkeypatch, source):
    home = failed_qa(tmp_path)
    restore = interrupt(monkeypatch, attempts, "archive_file", 0)
    assert invoke(home, *ROLLBACK)[0] == 1
    restore()
    path = plan_dir(home) / ".attempts/001/record.yaml"
    record = yaml.safe_load(path.read_text())
    record["files"][0]["source"] = source
    record["files"][0]["destination"] = ".attempts/001/files/" + source
    path.write_text(yaml.safe_dump(record))
    code, result = invoke(home, *INSTRUCTIONS, "requirements/proposal")
    assert code == 1 and result["error"] == "history_integrity"
    assert (plan_dir(home) / source).is_file()
