"""Gate PASS/FAIL outcome detection from output files."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .errors import GateOutputConflictError
from .models import GateOutputs


@dataclass(frozen=True)
class GateOutcome:
    status: str  # "PASS" / "FAIL"
    passed: bool
    path: Path
    summary: str | None
    blocking_issues: list[str]


def read_gate_outcome(artifact_dir: Path, outputs: GateOutputs) -> GateOutcome | None:
    """Return the gate's outcome, or None if neither pass nor fail exists yet."""

    pass_path = artifact_dir / outputs.pass_
    fail_path = artifact_dir / outputs.fail

    pass_exists = pass_path.is_file()
    fail_exists = fail_path.is_file()

    if pass_exists and fail_exists:
        raise GateOutputConflictError(
            f"Gate outputs conflict: both {outputs.pass_} and {outputs.fail} exist",
            fix=f"Remove one of {outputs.pass_} or {outputs.fail} so only one verdict remains.",
        )
    if not pass_exists and not fail_exists:
        return None

    if pass_exists:
        return GateOutcome(
            status="PASS",
            passed=True,
            path=pass_path.resolve(),
            summary=None,
            blocking_issues=[],
        )

    text = fail_path.read_text(encoding="utf-8")
    summary, issues = extract_failure_notes(text)
    return GateOutcome(
        status="FAIL",
        passed=False,
        path=fail_path.resolve(),
        summary=summary,
        blocking_issues=issues,
    )


def extract_failure_notes(text: str) -> tuple[str | None, list[str]]:
    """Best-effort extraction of a summary heading and bullet-list issues."""

    lines = [line.strip() for line in text.splitlines()]
    summary = next(
        (line.lstrip("#").strip() for line in lines if line.startswith("#")), None
    )
    issues = [line[2:].strip() for line in lines if line.startswith("- ") and line[2:].strip()]
    return summary, issues
