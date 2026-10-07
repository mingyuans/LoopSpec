"""In-place revisions of an approved Plan: preview, confirm and freeze rules (R1–R7)."""

from pathlib import Path

import yaml

from tests.workflow_helpers import (
    BUGFIX_FLOW,
    CHANGE,
    DOCS_FLOW,
    create_approved,
    fail_gate,
    invoke,
    node_status,
    pass_node,
    project,
    run_until,
    snapshot,
    status,
    write_request,
)

NOTES = {"id": "notes", "use": "requirements", "requires": ["requirements"]}


def revise(home: Path, flow: list[dict], base: int = 1, name: str = "revision.yaml"):
    request = write_request(home, flow, name=name, base_revision=base)
    code, preview = invoke(home, "plan", "validate", "-c", CHANGE, "-f", request)
    if code:
        return code, preview
    return invoke(
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


def test_preview_is_read_only_and_lists_additions(tmp_path: Path):
    home = project(tmp_path)
    create_approved(home, DOCS_FLOW)
    pass_node(home, "requirements/proposal")
    request = write_request(home, [*DOCS_FLOW, NOTES], name="revision.yaml", base_revision=1)
    before = snapshot(home)
    code, preview = invoke(home, "plan", "validate", "-c", CHANGE, "-f", request)
    assert code == 0, preview
    assert preview["mode"] == "revision" and preview["revision"] == 2
    assert preview["addedInstances"] == ["notes"] and preview["rerunNodes"] == []
    assert snapshot(home) == before
    assert status(home)["revision"] == 1


def test_adjusting_unstarted_work_keeps_progress(tmp_path: Path):
    home = project(tmp_path)
    create_approved(home, DOCS_FLOW)
    pass_node(home, "requirements/proposal")
    code, result = revise(home, [*DOCS_FLOW, NOTES])
    assert code == 0, result
    assert result["revision"] == 2 and result["rerunNodes"] == []
    assert node_status(home, "requirements/proposal") == "done"
    assert node_status(home, "notes/proposal") == "ready"
    meta = yaml.safe_load((home / "changes" / CHANGE / "plans/001/plan.yaml").read_text())["meta"]
    assert meta["revision"] == 2 and meta["digest"] == result["digest"]


def test_frozen_node_may_gain_requires_and_reruns_downstream(tmp_path: Path):
    home = project(tmp_path)
    create_approved(home, DOCS_FLOW)
    for identity in ("requirements/proposal", "design/design", "design/tasks"):
        pass_node(home, identity)
    extra = {"id": "extra", "use": "requirements"}
    flow = [DOCS_FLOW[0], extra, {**DOCS_FLOW[1], "requires": ["requirements", "extra"]}]
    code, result = revise(home, flow)
    assert code == 0, result
    assert result["rerunNodes"] == ["design/design", "design/tasks"]
    plan_dir = home / "changes" / CHANGE / "plans/001"
    record = yaml.safe_load((plan_dir / ".attempts/001/record.yaml").read_text())
    assert record["kind"] == "revision" and record["revision"] == 2
    assert {move["source"] for move in record["files"]} == {
        "artifacts/design/design.md",
        "artifacts/design/tasks.md",
    }
    assert (plan_dir / ".attempts/001/files/artifacts/design/design.md").is_file()
    assert node_status(home, "requirements/proposal") == "done"
    assert node_status(home, "design/design") == "blocked"
    history = invoke(home, "change", "history", CHANGE)[1]["attempts"]
    assert [item["kind"] for item in history] == ["revision"]


def test_frozen_nodes_cannot_be_removed_rewritten_or_lose_requires(tmp_path: Path):
    home = project(tmp_path)
    create_approved(home, DOCS_FLOW)
    for identity in ("requirements/proposal", "design/design"):
        pass_node(home, identity)
    for flow in (
        [DOCS_FLOW[0]],
        [DOCS_FLOW[0], {**DOCS_FLOW[1], "use": "requirements"}],
        [DOCS_FLOW[0], {**DOCS_FLOW[1], "requires": []}],
    ):
        code, result = revise(home, flow)
        assert code == 1 and result["error"] in ("node_frozen", "invalid_assurance"), result
        assert result["error"] == "node_frozen"
        assert "plan archive" in result["fix"]


def test_effective_fail_must_be_in_the_rerun_set(tmp_path: Path):
    home = project(tmp_path)
    create_approved(home, BUGFIX_FLOW)
    (tmp_path / "backend/code.py").write_text("changed\n")
    run_until(home, "qa/test")
    fail_gate(home, "qa/test")
    unrelated = [*BUGFIX_FLOW[:3], NOTES, BUGFIX_FLOW[3]]
    unrelated[4] = {**BUGFIX_FLOW[3], "requires": ["qa", "notes"]}
    code, result = revise(home, unrelated)
    assert code == 1 and result["error"] == "failure_pending"
    covering = [*BUGFIX_FLOW[:2], NOTES, {**BUGFIX_FLOW[2], "requires": ["be", "notes"]}]
    code, result = revise(home, [*covering, BUGFIX_FLOW[3]])
    assert code == 0, result
    assert "qa/test" in result["rerunNodes"]
    assert node_status(home, "qa/test") == "blocked"


def test_stale_base_revision_and_concurrent_revisions(tmp_path: Path):
    home = project(tmp_path)
    create_approved(home, DOCS_FLOW)
    code, result = revise(home, [*DOCS_FLOW, NOTES], base=2)
    assert code == 1 and result["error"] == "stale_revision"
    first = write_request(home, [*DOCS_FLOW, NOTES], name="a.yaml", base_revision=1)
    second_flow = [*DOCS_FLOW, {**NOTES, "id": "other"}]
    second = write_request(home, second_flow, name="b.yaml", base_revision=1)
    digest_a = invoke(home, "plan", "validate", "-c", CHANGE, "-f", first)[1]["digest"]
    digest_b = invoke(home, "plan", "validate", "-c", CHANGE, "-f", second)[1]["digest"]
    args = ("plan", "approve", "-c", CHANGE, "-p", "001")
    assert invoke(home, *args, "-f", first, "--digest", digest_a)[0] == 0
    code, result = invoke(home, *args, "-f", second, "--digest", digest_b)
    assert code == 1 and result["error"] == "stale_revision"


def test_revision_needs_the_previewed_digest(tmp_path: Path):
    home = project(tmp_path)
    create_approved(home, DOCS_FLOW)
    request = write_request(home, [*DOCS_FLOW, NOTES], name="revision.yaml", base_revision=1)
    code, result = invoke(
        home, "plan", "approve", "-c", CHANGE, "-p", "001", "-f", request, "--digest", "0" * 64
    )
    assert code == 1 and result["error"] == "plan_changed"
    assert status(home)["revision"] == 1


def test_revision_makes_code_evidence_stale(tmp_path: Path):
    home = project(tmp_path)
    create_approved(home, BUGFIX_FLOW)
    (tmp_path / "backend/code.py").write_text("changed\n")
    run_until(home, "be/security/check")
    assert node_status(home, "be/tests/check") == "done"
    flow = [
        *BUGFIX_FLOW[:2],
        NOTES,
        {**BUGFIX_FLOW[2], "requires": ["be", "notes"]},
        BUGFIX_FLOW[3],
    ]
    code, result = revise(home, flow)
    assert code == 0, result
    entry = next(n for n in status(home)["nodes"] if n["id"] == "be/tests/check")
    assert entry["status"] == "ready" and entry["reason"] == "evidence_stale"


def test_revision_keeps_rollback_counts(tmp_path: Path):
    home = project(tmp_path)
    create_approved(home, BUGFIX_FLOW)
    (tmp_path / "backend/code.py").write_text("changed\n")
    run_until(home, "qa/test")
    fail_gate(home, "qa/test")
    assert invoke(home, "plan", "rollback", "-c", CHANGE, "-p", "001")[0] == 0
    flow = [
        *BUGFIX_FLOW[:2],
        NOTES,
        {**BUGFIX_FLOW[2], "requires": ["be", "notes"]},
        BUGFIX_FLOW[3],
    ]
    assert revise(home, flow)[0] == 0
    run_until(home, "qa/test")
    fail_gate(home, "qa/test")
    entry = next(n for n in status(home)["nodes"] if n["id"] == "qa/test")
    assert entry["gate"]["rollbacksUsed"] == 1


def test_gate_with_rework_history_cannot_be_renamed(tmp_path: Path):
    home = project(tmp_path)
    create_approved(home, BUGFIX_FLOW)
    (tmp_path / "backend/code.py").write_text("changed\n")
    run_until(home, "qa/test")
    fail_gate(home, "qa/test")
    assert invoke(home, "plan", "rollback", "-c", CHANGE, "-p", "001")[0] == 0
    renamed = [*BUGFIX_FLOW[:2], {**BUGFIX_FLOW[2], "id": "acceptance"}]
    renamed.append({**BUGFIX_FLOW[3], "requires": ["acceptance"]})
    code, result = revise(home, renamed)
    assert code == 1 and result["error"] == "node_frozen"
