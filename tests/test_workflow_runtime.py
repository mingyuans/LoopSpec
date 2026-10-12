"""Navigation of the active Plan: leaves execute, references only summarise (D7)."""

from pathlib import Path

from loopspec.workflow_evidence import valid_evidence
from loopspec.workflow_io import atomic_write
from loopspec.workflow_models import ResolvedGate
from tests.test_workflow_catalog import fragment_path
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


FANOUT_FLOW = [
    {"id": "prd", "use": "requirements"},
    {"id": "fe-review", "use": "requirements", "requires": ["prd"]},
    {"id": "be-review", "use": "requirements", "requires": ["prd"]},
    {"id": "qa-review", "use": "requirements", "requires": ["prd"]},
    {
        "id": "review-gate",
        "use": "qa-testing",
        "requires": ["fe-review", "be-review", "qa-review"],
        "on_fail": {"reset": ["prd"], "max_retries": 1},
    },
]
# Dependency order: the compiler breaks ties between independent nodes by id.
REVIEWS = ["be-review/proposal", "fe-review/proposal", "qa-review/proposal"]


def node_steps(*identities: str) -> list[str]:
    return [f"loopspec node instructions -c {CHANGE} -n {identity}" for identity in identities]


def test_parallel_ready_leaves_are_all_listed(tmp_path: Path):
    home = project(tmp_path, code=False)
    create_approved(home, FANOUT_FLOW)
    report = status(home)
    assert report["nextSteps"] == node_steps("prd/proposal")
    assert report["parallel"] is False
    pass_node(home, "prd/proposal")
    report = status(home)
    assert report["nextSteps"] == node_steps(*REVIEWS)
    assert report["parallel"] is True
    assert node_status(home, "review-gate/test") == "blocked"
    for done, remaining in ((1, REVIEWS[1:]), (2, REVIEWS[2:])):
        pass_node(home, REVIEWS[done - 1])
        report = status(home)
        assert report["nextSteps"] == node_steps(*remaining)
        assert report["parallel"] is (len(remaining) > 1)
        assert node_status(home, "review-gate/test") == "blocked"
    pass_node(home, REVIEWS[2])
    report = status(home)
    assert report["nextSteps"] == node_steps("review-gate/test")
    assert report["parallel"] is False


def test_linear_plan_keeps_a_single_step(tmp_path: Path):
    home = project(tmp_path, code=False)
    create_approved(home, MANUAL_FLOW)
    report = status(home)
    assert report["nextSteps"] == node_steps("requirements/proposal")
    assert report["parallel"] is False


def test_rollback_and_exhaustion_override_parallel_steps(tmp_path: Path):
    home = project(tmp_path, code=False)
    create_approved(home, FANOUT_FLOW)
    for identity in ("prd/proposal", *REVIEWS):
        pass_node(home, identity)
    fail_gate(home, "review-gate/test")
    report = status(home)
    assert report["nextSteps"] == [f"loopspec plan rollback -c {CHANGE} -p 001"]
    assert report["parallel"] is False
    code, result = invoke(home, "plan", "rollback", "-c", CHANGE, "-p", "001")
    assert code == 0, result
    for identity in ("prd/proposal", *REVIEWS):
        pass_node(home, identity)
    fail_gate(home, "review-gate/test")
    report = status(home)
    assert node_status(home, "review-gate/test") == "exhausted"
    assert report["nextSteps"] == [] and report["parallel"] is False


def test_change_next_lists_every_target_node(tmp_path: Path):
    home = project(tmp_path, code=False)
    create_approved(home, FANOUT_FLOW)
    pass_node(home, "prd/proposal")
    code, result = invoke(home, "change", "next", CHANGE)
    assert code == 0, result
    assert result["node"]["id"] == REVIEWS[0]
    assert [node["id"] for node in result["nodes"]] == REVIEWS
    assert result["parallel"] is True
    assert result["nextSteps"] == node_steps(*REVIEWS)
    for identity in REVIEWS:
        pass_node(home, identity)
    fail_gate(home, "review-gate/test")
    code, result = invoke(home, "change", "next", CHANGE)
    assert result["node"]["id"] == "review-gate/test"
    assert [node["id"] for node in result["nodes"]] == ["review-gate/test"]
    assert result["parallel"] is False


def test_parallel_is_false_outside_active_execution(tmp_path: Path):
    home = project(tmp_path, code=False)
    new_change(home)
    assert status(home)["parallel"] is False
    create_draft(home, DOCS_FLOW)
    assert status(home)["parallel"] is False
    approve(home, "001")
    for identity in ("requirements/proposal", "design/design", "design/tasks"):
        pass_node(home, identity)
    report = status(home)
    assert report["isComplete"] and report["parallel"] is False
