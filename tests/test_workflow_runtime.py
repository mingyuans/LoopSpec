"""Navigation of the active Plan: leaves execute, references only summarise (D7)."""

from pathlib import Path

from loopspec.workflow_evidence import valid_evidence
from loopspec.workflow_io import atomic_write
from loopspec.workflow_models import ResolvedGate
from tests.test_workflow_catalog import fragment_path
from tests.workflow_helpers import (
    CHANGE,
    create_approved,
    invoke,
    loaded,
    project,
    status,
)

MANUAL_FLOW = [
    {"id": "requirements", "use": "requirements"},
    {"id": "design", "use": "design", "requires": ["requirements"]},
    {"id": "implementation", "use": "backend-code", "requires": ["design"]},
    {"id": "qa", "use": "qa-testing", "requires": ["implementation"]},
]


def complete_output(root: Path, path: str, body: str = "已完成"):
    atomic_write(root, path, body.encode())


def instructions(home: Path, identity: str):
    return invoke(home, "node", "instructions", "-c", CHANGE, "-n", identity)


def test_leaves_execute_and_references_only_summarize(tmp_path: Path):
    home = project(tmp_path, code=False)
    plan = create_approved(home, MANUAL_FLOW)
    report = status(home)
    assert report["nodes"][0]["status"] == "ready"
    assert invoke(home, "change", "next", CHANGE)[1]["nextSteps"] == report["nextSteps"]
    code, result = instructions(home, "requirements")
    assert code == 1 and result["error"] == "reference_not_executable"
    for node in report["nodes"]:
        code, result = instructions(home, node["id"])
        assert code == 0, result
        assert "instruction" in result
        path = node["outputPath"]
        complete_output(plan.root, path["pass"] if isinstance(path, dict) else path)
    final = status(home)
    assert final["isComplete"]
    assert {item["id"] for item in final["instances"]} >= {"requirements", "design", "qa"}
    assert all(item["status"] == "done" for item in final["instances"])


def test_outputs_live_in_the_plan_directory(tmp_path: Path):
    home = project(tmp_path, code=False)
    create_approved(home, MANUAL_FLOW)
    entry = status(home)["nodes"][0]
    assert entry["resolvedOutputPath"] == str(
        home / "changes" / CHANGE / "plans/001/artifacts/requirements/proposal.md"
    )


def test_missing_report_is_not_failure_conflict_or_malformed_is_error(tmp_path: Path):
    home = project(tmp_path, code=False)
    root = create_approved(home, MANUAL_FLOW).root
    for path in (
        "artifacts/requirements/proposal.md",
        "artifacts/design/design.md",
        "artifacts/design/tasks.md",
        "artifacts/implementation/implementation.md",
    ):
        complete_output(root, path)
    report = status(home)
    qa = next(node for node in report["nodes"] if node["id"] == "qa/test")
    assert qa["status"] == "ready"
    assert report["pendingRollback"] is None
    complete_output(root, "artifacts/qa/test/fail.md", "缺失 verdict")
    assert invoke(home, "change", "status", CHANGE)[1]["error"] == "invalid_verdict"
    complete_output(root, "artifacts/qa/test/pass.md")
    assert invoke(home, "change", "status", CHANGE)[1]["error"] == "verdict_conflict"


def test_failed_gate_without_on_fail_is_exhausted(tmp_path: Path):
    home = project(tmp_path, code=False)
    root = create_approved(home, MANUAL_FLOW).root
    for path in (
        "artifacts/requirements/proposal.md",
        "artifacts/design/design.md",
        "artifacts/design/tasks.md",
        "artifacts/implementation/implementation.md",
    ):
        complete_output(root, path)
    complete_output(root, "artifacts/qa/test/fail.md", "verdict: FAIL\nsummary: 缺陷\n")
    report = status(home)
    assert report["nodes"][-1]["status"] == "exhausted"
    assert report["nextSteps"] == []


def test_code_gate_cannot_pass_by_manual_file(tmp_path: Path):
    home = project(tmp_path, code=False)
    plan = create_approved(home, MANUAL_FLOW)
    node = plan.spec.nodes[-1].model_copy(deep=True)
    node.gate = ResolvedGate.model_validate(
        {
            "outputs": {"pass": "p", "fail": "f"},
            "evidence": {"provides": ["review"], "paths": ["src/**"]},
        }
    )
    assert valid_evidence(plan, node) == (False, "evidence_missing")


def test_instructions_and_templates_are_read_live(tmp_path: Path):
    home = project(tmp_path, code=False)
    create_approved(home, MANUAL_FLOW)
    (home / "fragments/requirements/proposal.instruction.md").write_text("最新指令")
    (home / "fragments/requirements/proposal.template.md").write_text("最新模板")
    code, result = instructions(home, "requirements/proposal")
    assert code == 0 and result["instruction"] == "最新指令"
    assert result["template"] == "最新模板"


def test_fragment_definition_changes_do_not_alter_the_approved_graph(tmp_path: Path):
    home = project(tmp_path, code=False)
    create_approved(home, MANUAL_FLOW)
    before = loaded(home).spec
    fragment_path(home, "requirements").write_text("corrupted")
    assert invoke(home, "change", "status", CHANGE)[0] == 0
    assert instructions(home, "requirements/proposal")[0] == 0
    assert loaded(home).spec == before


def test_gate_protocol_uses_the_command_tree(tmp_path: Path):
    from tests.workflow_helpers import BUGFIX_FLOW, run_until

    home = project(tmp_path)
    create_approved(home, BUGFIX_FLOW)
    (tmp_path / "backend/code.py").write_text("changed\n")
    run_until(home, "be/tests/check")
    result = instructions(home, "be/tests/check")[1]
    assert result["gateProtocol"]["beginCommand"] == (
        f"loopspec gate begin -c {CHANGE} -n be/tests/check"
    )
    run_until(home, "assurance/check")
    result = instructions(home, "assurance/check")[1]
    assert result["gateProtocol"] == {
        "kind": "assurance",
        "recordCommand": f"loopspec gate record -c {CHANGE} -n assurance/check",
    }
