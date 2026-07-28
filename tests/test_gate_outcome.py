from pathlib import Path

import pytest

from loopspec.errors import GateOutputConflictError
from loopspec.gate_outcome import extract_failure_notes, read_gate_outcome
from loopspec.models import GateOutputs


def make_outputs() -> GateOutputs:
    return GateOutputs(**{"pass": "security/pass.md", "fail": "security/fail.md"})


def test_pass_only_yields_pass_outcome(tmp_path: Path):
    (tmp_path / "security").mkdir()
    (tmp_path / "security" / "pass.md").write_text("# ok")

    outcome = read_gate_outcome(tmp_path, make_outputs())
    assert outcome is not None
    assert outcome.status == "PASS"
    assert outcome.passed is True


def test_fail_only_yields_fail_outcome(tmp_path: Path):
    (tmp_path / "security").mkdir()
    (tmp_path / "security" / "fail.md").write_text("# Blocked\n\n- issue one")

    outcome = read_gate_outcome(tmp_path, make_outputs())
    assert outcome is not None
    assert outcome.status == "FAIL"
    assert outcome.passed is False


def test_neither_exists_returns_none(tmp_path: Path):
    assert read_gate_outcome(tmp_path, make_outputs()) is None


def test_both_exist_raises_conflict(tmp_path: Path):
    (tmp_path / "security").mkdir()
    (tmp_path / "security" / "pass.md").write_text("# ok")
    (tmp_path / "security" / "fail.md").write_text("# no")

    with pytest.raises(GateOutputConflictError):
        read_gate_outcome(tmp_path, make_outputs())


def test_extract_failure_notes_heading_and_list():
    text = "# 安全审查未通过\n\n## 阻断问题\n\n- issue A\n- issue B\n"
    summary, issues = extract_failure_notes(text)
    assert summary == "安全审查未通过"
    assert issues == ["issue A", "issue B"]


def test_extract_failure_notes_no_extractable_content():
    summary, issues = extract_failure_notes("just plain prose, nothing structured")
    assert summary is None
    assert issues == []
