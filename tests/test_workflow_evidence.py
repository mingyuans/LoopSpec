import json
from pathlib import Path

import pytest

from loopspec.errors import WorkflowError
from loopspec.workflow_evidence import begin, record, valid_evidence
from loopspec.workflow_io import atomic_write
from loopspec.workflow_runtime import status
from tests.test_workflow_diff import activate, fixture
from tests.workflow_helpers import invoke


def report(loaded, verdict="PASS"):
    atomic_write(
        loaded.root,
        "artifacts/review-draft.md",
        json.dumps({"verdict": verdict, "summary": "实际审查结果"}).encode(),
    )
    return "artifacts/review-draft.md"


def test_begin_record_binds_scope_and_report_not_self_reported(tmp_path: Path):
    home = fixture(tmp_path)
    (tmp_path / "initial.md").write_text("reviewed changes")
    loaded = activate(home)
    context = begin(loaded.home, "AFD1111", "check/review")
    assert context["paths"][0]["path"] == "initial.md"
    assert "reviewed changes" not in json.dumps(context)
    result = record(loaded.home, "AFD1111", "check/review", context["roundId"], report(loaded))
    assert result["evidenceRecorded"]
    assert valid_evidence(loaded, loaded.spec.nodes[0]) == (True, None)
    assert status(loaded)["isComplete"]
    with pytest.raises(WorkflowError):
        record(loaded.home, "AFD1111", "check/review", context["roundId"], report(loaded))
    (tmp_path / "initial.md").write_text("changed after review")
    node = status(loaded)["nodes"][0]
    assert node["status"] == "ready"
    assert node["reason"] == "evidence_stale"


def test_changes_during_review_require_fresh_begin(tmp_path: Path):
    loaded = activate(fixture(tmp_path))
    context = begin(loaded.home, "AFD1111", "check/review")
    (tmp_path / "initial.md").write_text("change while reviewing")
    with pytest.raises(WorkflowError, match="审查期间"):
        record(loaded.home, "AFD1111", "check/review", context["roundId"], report(loaded))
    fresh = begin(loaded.home, "AFD1111", "check/review")
    with pytest.raises(WorkflowError, match="编号"):
        record(loaded.home, "AFD1111", "check/review", context["roundId"], report(loaded))
    assert record(loaded.home, "AFD1111", "check/review", fresh["roundId"], report(loaded))[
        "evidenceRecorded"
    ]


def test_manual_fail_without_bound_evidence_is_not_business_failure(tmp_path: Path):
    loaded = activate(fixture(tmp_path))
    atomic_write(loaded.root, "artifacts/check/f.md", b"verdict: FAIL\nsummary: handwritten\n")
    node = status(loaded)["nodes"][0]
    assert node["status"] == "ready"
    assert node["reason"] == "evidence_missing"


def test_cli_protocol_and_reject_arbitrary_scope_fields(tmp_path: Path):
    home = fixture(tmp_path)
    loaded = activate(home)
    code, context = invoke(home, "gate", "begin", "-c", "AFD1111", "-n", "check/review")
    assert code == 0
    path = report(loaded)
    atomic_write(loaded.root, path, b"verdict: PASS\nsummary: fake\nscope_digest: arbitrary\n")
    result = invoke(
        home,
        "gate",
        "record",
        "-c",
        "AFD1111",
        "-n",
        "check/review",
        "--round",
        context["roundId"],
        "--report",
        path,
    )
    assert result[0] == 1
    assert result[1]["error"] == "invalid_verdict"
    path = report(loaded)
    assert (
        invoke(
            home,
            "gate",
            "record",
            "-c",
            "AFD1111",
            "-n",
            "check/review",
            "--round",
            context["roundId"],
            "--report",
            path,
        )[0]
        == 0
    )


def test_report_must_live_in_the_active_plan_artifacts(tmp_path: Path):
    loaded = activate(fixture(tmp_path))
    context = begin(loaded.home, "AFD1111", "check/review")
    atomic_write(loaded.change.root, "draft.md", b"verdict: PASS\nsummary: x\n")
    with pytest.raises(WorkflowError) as error:
        record(loaded.home, "AFD1111", "check/review", context["roundId"], "../../draft.md")
    assert error.value.code == "unsafe_path"


def test_code_gate_needs_round_and_report(tmp_path: Path):
    home = fixture(tmp_path)
    activate(home)
    code, result = invoke(home, "gate", "record", "-c", "AFD1111", "-n", "check/review")
    assert code == 1 and result["error"] == "option_required"
