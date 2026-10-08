"""Gate control files under .gates/ and .gate-rounds/ are YAML; old JSON ones still read."""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from loopspec.workflow_io import atomic_write
from tests.workflow_helpers import (
    BUGFIX_FLOW,
    CHANGE,
    create_approved,
    invoke,
    loaded,
    node_status,
    pass_node,
    project,
    run_until,
)

GATE = "be/tests/check"


def is_block_yaml(path: Path) -> bool:
    text = path.read_text()
    return not text.lstrip().startswith("{") and text.count("\n") > 1


def started(tmp_path: Path) -> tuple[Path, Path]:
    home = project(tmp_path)
    create_approved(home, BUGFIX_FLOW)
    (tmp_path / "backend/code.py").write_text("changed\n")
    run_until(home, GATE)
    return home, loaded(home).root


def as_json(path: Path) -> None:
    """Rewrite a control file the way releases before this fix wrote it."""
    data = yaml.safe_load(path.read_text())
    path.write_text(json.dumps(data, sort_keys=True, separators=(",", ":")) + "\n")


# Y1
def test_gate_begin_writes_yaml(tmp_path: Path):
    home, root = started(tmp_path)
    code, context = invoke(home, "gate", "begin", "-c", CHANGE, "-n", GATE)
    assert code == 0, context
    for path in (root / f".gates/{GATE}/begin.yaml", root / f".gate-rounds/{GATE}/001.yaml"):
        assert is_block_yaml(path), path
        data = yaml.safe_load(path.read_text())
        assert data["round_id"] == context["roundId"]
        assert data["scope_digest"] == context["scopeDigest"]
        assert data["baseline"] == context["baseline"]
        assert data["plan_digest"] == context["planDigest"]


# Y2
def test_code_gate_record_writes_yaml_evidence(tmp_path: Path):
    home, root = started(tmp_path)
    pass_node(home, GATE)
    path = root / f".gates/{GATE}/evidence.yaml"
    assert is_block_yaml(path)
    evidence = yaml.safe_load(path.read_text())
    assert evidence["verdict"] == "PASS" and len(evidence["report_hash"]) == 64


# Y3, Y4
def test_assurance_record_writes_yaml_and_no_json_remains(tmp_path: Path):
    home, root = started(tmp_path)
    run_until(home, "assurance/check")
    pass_node(home, "assurance/check")
    assert node_status(home, "assurance/check") == "done"
    for name in ("assurance.yaml", "evidence.yaml"):
        assert is_block_yaml(root / ".gates/assurance/check" / name), name
    rounds = sorted((root / ".gate-rounds/assurance/check").glob("*.yaml"))
    assert rounds and all(is_block_yaml(path) for path in rounds)
    offenders = [
        str(path.relative_to(root))
        for path in root.rglob("*.yaml")
        if path.read_text().lstrip().startswith("{")
    ]
    assert offenders == []


# Y5
def test_old_json_control_files_still_read(tmp_path: Path):
    home, root = started(tmp_path)
    pass_node(home, GATE)
    for name in ("begin.yaml", "evidence.yaml"):
        as_json(root / f".gates/{GATE}/{name}")
    assert node_status(home, GATE) == "done"
    code, context = invoke(home, "gate", "begin", "-c", CHANGE, "-n", "be/security/check")
    assert code == 0, context
    as_json(root / ".gates/be/security/check/begin.yaml")
    report = "artifacts/reports/security.yaml"
    atomic_write(root, report, "verdict: PASS\nsummary: 模拟审查通过\n".encode())
    code, result = invoke(
        home, "gate", "record", "-c", CHANGE, "-n", "be/security/check",
        "--round", context["roundId"], "--report", report,
    )  # fmt: skip
    assert code == 0 and result["verdict"] == "PASS", result
    assert node_status(home, "be/security/check") == "done"
