import json
from pathlib import Path

import pytest

from loopspec.errors import WorkflowError
from loopspec.workflow_assurance import diagnose
from loopspec.workflow_evidence import begin, record
from loopspec.workflow_git import git
from loopspec.workflow_io import atomic_write
from loopspec.workflow_models import PlanRequest
from loopspec.workflow_planning import compile_request
from loopspec.workflow_runtime import status
from tests.test_workflow_catalog import fragment_path
from tests.workflow_helpers import create_approved, init_repository, invoke


def fixture(tmp_path: Path, backend=False, unknown=None, project_unknown=None):
    init_repository(tmp_path)
    home = tmp_path / "loopspec"
    home.mkdir()
    (home / "config.yaml").write_text("workflow: {}\n")
    if project_unknown is not None:
        (home / "config.yaml").write_text("workflow:\n  assurance_rules: project-rules.yaml\n")
        (home / "project-rules.yaml").write_text(
            json.dumps(
                {
                    "unknown_paths": project_unknown,
                    "rules": [
                        {
                            "id": "project-docs",
                            "paths": ["docs/**"],
                            "requires": ["pr-review"],
                            "repair_fragment": "frontend-implementation",
                        }
                    ],
                }
            )
        )
    for name, capabilities in {
        "frontend": ["frontend-tests", "pr-review"],
        "backend": ["backend-tests", "security-review", "pr-review"],
    }.items():
        (tmp_path / name).mkdir()
        (tmp_path / name / "code.py").write_text("original")
        fragment_path(home, name + "-implementation").write_text(
            json.dumps(
                {
                    "name": name + "-implementation",
                    "nodes": [
                        {"id": "implement", "generates": "implementation.md"},
                        {
                            "id": "review",
                            "requires": ["implement"],
                            "gate": {
                                "outputs": {"pass": "p.md", "fail": "f.md"},
                                "evidence": {"provides": capabilities, "paths": [name + "/**"]},
                            },
                        },
                    ],
                }
            )
        )
    fragment_path(home, "qa").write_text(
        json.dumps(
            {
                "name": "qa",
                "nodes": [{"id": "test", "gate": {"outputs": {"pass": "p.md", "fail": "f.md"}}}],
            }
        )
    )
    fragment_path(home, "assurance").write_text(
        json.dumps(
            {
                "name": "assurance",
                "nodes": [
                    {
                        "id": "check",
                        "gate": {
                            "outputs": {"pass": "p.md", "fail": "f.md"},
                            "assurance": "rules.yaml",
                        },
                    }
                ],
            }
        )
    )
    (home / "fragments/assurance/rules.yaml").write_text(
        json.dumps(
            {
                **({"unknown_paths": unknown} if unknown is not None else {}),
                "rules": [
                    {
                        "id": "frontend",
                        "paths": ["frontend/**"],
                        "requires": ["frontend-tests", "pr-review"],
                        "repair_fragment": "frontend-implementation",
                    },
                    {
                        "id": "backend",
                        "paths": ["backend/**"],
                        "requires": ["backend-tests", "security-review", "pr-review"],
                        "repair_fragment": "backend-implementation",
                    },
                ],
            }
        )
    )
    implementations = [{"id": "fe", "use": "frontend-implementation"}]
    if backend:
        implementations.append({"id": "be", "use": "backend-implementation"})
    flow = [
        *implementations,
        {"id": "qa", "use": "qa", "requires": [item["id"] for item in implementations]},
        {"id": "assurance", "use": "assurance", "requires": ["qa"]},
    ]
    git(tmp_path, ["add", "."])
    git(tmp_path, ["commit", "-q", "-m", "assurance fixture"])
    return home, create_approved(home, flow)


def loaded_flow(home: Path) -> list[dict]:
    from tests.workflow_helpers import loaded

    return [ref.model_dump(exclude_none=True) for ref in loaded(home).spec.flow]


def check(loaded):
    code, result = invoke(loaded.home, "gate", "record", "-c", "AFD1111", "-n", "assurance/check")
    assert code == 0, result
    return result


def review(loaded, instance: str):
    atomic_write(loaded.root, f"artifacts/{instance}/implementation.md", "实施结果".encode())
    context = begin(loaded.home, "AFD1111", instance + "/review")
    atomic_write(loaded.root, "artifacts/draft.md", b"verdict: PASS\nsummary: actual review\n")
    record(loaded.home, "AFD1111", instance + "/review", context["roundId"], "artifacts/draft.md")


def qa(loaded):
    atomic_write(loaded.root, "artifacts/qa/p.md", "实际回归测试通过".encode())


def test_deterministic_pass_and_code_changes_stale_entire_delivery(tmp_path: Path):
    _, loaded = fixture(tmp_path)
    (tmp_path / "frontend/code.py").write_text("first implementation")
    review(loaded, "fe")
    qa(loaded)
    result = check(loaded)
    assert result["verdict"] == "PASS"
    assert status(loaded)["isComplete"]
    before = diagnose(loaded)["diffDigest"]
    atomic_write(loaded.root, "artifacts/extra-report.md", b"report")
    assert diagnose(loaded)["diffDigest"] == before
    (tmp_path / "frontend/code.py").write_text("later unreviewed edit")
    assert diagnose(loaded)["stale_evidence"]
    report = status(loaded)
    assert not report["isComplete"]
    assert report["nodes"][-1]["status"] == "blocked"


def test_frontend_plan_touches_backend_reports_missing_fragment(tmp_path: Path):
    _, loaded = fixture(tmp_path)
    (tmp_path / "frontend/code.py").write_text("frontend implementation")
    (tmp_path / "backend/code.py").write_text("unexpected backend edit")
    review(loaded, "fe")
    qa(loaded)
    result = check(loaded)
    assert result["verdict"] == "FAIL"
    assert {item["capability"] for item in result["missing_fragments"]} == {
        "backend-tests",
        "security-review",
        "pr-review",
    }
    assert all(
        item["fragments"] == ["backend-implementation"] for item in result["missing_fragments"]
    )
    assert not result["unknown_paths"]


def test_unknown_directory_and_handwritten_assurance_pass_are_not_accepted(tmp_path: Path):
    _, loaded = fixture(tmp_path)
    review(loaded, "fe")
    qa(loaded)
    atomic_write(loaded.root, "artifacts/assurance/p.md", b"handwritten pass")
    assert not status(loaded)["isComplete"]
    (tmp_path / "unknown.py").write_text("unknown change")
    result = check(loaded)
    assert result["verdict"] == "FAIL"
    assert result["unknown_paths"] == ["unknown.py"]


def test_backend_evidence_cannot_be_substituted_by_frontend_instance(tmp_path: Path):
    _, loaded = fixture(tmp_path, backend=True)
    (tmp_path / "backend/code.py").write_text("backend implementation")
    review(loaded, "fe")
    result = diagnose(loaded)
    assert result["missing_evidence"]
    assert not result["missing_fragments"]
    assert all(item["gates"] == ["be/review"] for item in result["missing_evidence"])
    review(loaded, "be")
    qa(loaded)
    assert check(loaded)["verdict"] == "PASS"


def test_final_assurance_cannot_leave_parallel_branch_uncovered(tmp_path: Path):
    home, _ = fixture(tmp_path)
    request = {"flow": [*loaded_flow(home), {"id": "be", "use": "backend-implementation"}]}
    with pytest.raises(WorkflowError, match="覆盖所有交付分支"):
        compile_request(home, PlanRequest.model_validate(request))


def test_code_review_cannot_be_ordered_after_final_assurance(tmp_path: Path):
    home, _ = fixture(tmp_path)
    request = {
        "flow": [
            *loaded_flow(home),
            {"id": "be", "use": "backend-implementation", "requires": ["assurance"]},
        ]
    }
    with pytest.raises(WorkflowError, match="代码审查必须先于"):
        compile_request(home, PlanRequest.model_validate(request))


def test_archive_rechecks_stale_gate_and_assurance(tmp_path: Path):
    home, loaded = fixture(tmp_path)
    (tmp_path / "frontend/code.py").write_text("reviewed implementation")
    review(loaded, "fe")
    qa(loaded)
    check(loaded)
    assert invoke(home, "change", "archive", "AFD1111", "--dry-run")[0] == 0
    (tmp_path / "frontend/code.py").write_text("unreviewed later edit")
    code, result = invoke(home, "change", "archive", "AFD1111", "--dry-run")
    assert code == 1
    assert result["error"] == "archive_unsafe"
    assert loaded.root.is_dir()


def test_assurance_record_takes_no_round_or_report(tmp_path: Path):
    home, loaded = fixture(tmp_path)
    code, result = invoke(
        home,
        "gate",
        "record",
        "-c",
        "AFD1111",
        "-n",
        "assurance/check",
        "--round",
        "x",
        "--report",
        "artifacts/x.md",
    )
    assert code == 1 and result["error"] == "option_conflict"


def test_blocked_assurance_reports_without_recording(tmp_path: Path):
    _, loaded = fixture(tmp_path)
    result = check(loaded)
    assert result["recorded"] is False and result["blockedBy"]
    assert not (loaded.root / "artifacts/assurance/check/p.md").exists()


def test_live_rules_take_effect_immediately(tmp_path: Path):
    home, loaded = fixture(tmp_path)
    (tmp_path / "docs.md").write_text("new docs")
    review(loaded, "fe")
    qa(loaded)
    assert check(loaded)["unknown_paths"] == ["docs.md"]
    rules = json.loads((home / "fragments/assurance/rules.yaml").read_text())
    rules["rules"].append(
        {
            "id": "docs",
            "paths": ["*.md", "loopspec/**"],
            "requires": ["pr-review"],
            "repair_fragment": "frontend-implementation",
        }
    )
    (home / "fragments/assurance/rules.yaml").write_text(json.dumps(rules))
    assert check(loaded)["unknown_paths"] == []


def ignore_local_files(tmp_path: Path) -> None:
    # Inside frontend/ so the ignore file itself is covered by the frontend review.
    (tmp_path / "frontend/.gitignore").write_text("*.local\n")
    git(tmp_path, ["add", "frontend/.gitignore"])
    git(tmp_path, ["commit", "-q", "-m", "ignore local files"])


def test_ignored_paths_are_warned_in_assurance_report_and_outputs(tmp_path: Path):
    _, loaded = fixture(tmp_path)
    ignore_local_files(tmp_path)
    (tmp_path / "frontend/code.py").write_text("implementation")
    (tmp_path / "frontend/secret.local").write_text("ignored")
    atomic_write(loaded.root, "artifacts/fe/implementation.md", "实施结果".encode())
    context = begin(loaded.home, "AFD1111", "fe/review")
    expected = {"ignoredPaths": ["frontend/secret.local"], "ignoredTotal": 1}
    assert context["warnings"] == expected
    atomic_write(loaded.root, "artifacts/draft.md", b"verdict: PASS\nsummary: actual review\n")
    recorded = record(loaded.home, "AFD1111", "fe/review", context["roundId"], "artifacts/draft.md")
    assert recorded["warnings"] == expected
    assert status(loaded)["warnings"] == expected
    qa(loaded)
    result = check(loaded)
    assert result["verdict"] == "PASS"
    assert result["warnings"] == expected
    report = (loaded.root / "artifacts/assurance/p.md").read_text()
    assert "1 条告警" in report
    assert "frontend/secret.local" in report
    diagnostics = (loaded.root / ".gates/assurance/check/assurance.yaml").read_text()
    assert "frontend/secret.local" in diagnostics
    assert status(loaded)["isComplete"]


def test_assurance_report_without_warnings_is_unchanged(tmp_path: Path):
    _, loaded = fixture(tmp_path)
    (tmp_path / "frontend/code.py").write_text("implementation")
    review(loaded, "fe")
    qa(loaded)
    result = check(loaded)
    assert result["warnings"] is None
    report = (loaded.root / "artifacts/assurance/p.md").read_text()
    assert "告警" not in report
    assert "warnings" not in status(loaded)


def test_failed_assurance_with_warnings_can_be_rolled_back(tmp_path: Path):
    home, loaded = fixture(tmp_path)
    ignore_local_files(tmp_path)
    (tmp_path / "frontend/code.py").write_text("implementation")
    (tmp_path / "frontend/notes.local").write_text("ignored")
    review(loaded, "fe")
    qa(loaded)
    (tmp_path / "unknown.py").write_text("unknown change")
    result = check(loaded)
    assert result["verdict"] == "FAIL"
    assert "告警" in (loaded.root / "artifacts/assurance/f.md").read_text()
    assert status(loaded)["nodes"][-1]["status"] in {"failed", "exhausted"}


def test_warning_text_keeps_failure_summary_within_report_limit():
    from loopspec.workflow_assurance import warning_text
    from loopspec.workflow_models import FailureReport

    paths = [f"{index:02d}/" + "d" * 4000 for index in range(20)]
    text = warning_text({"ignoredPaths": paths, "ignoredTotal": 37})
    summary = "全量 Diff 保障存在缺口，请按诊断补齐审查或修订 Plan" + text
    FailureReport.model_validate({"verdict": "FAIL", "summary": summary})
    assert "37 条告警" in text
    assert paths[0] in text
    assert paths[-1] not in text
    assert "未列出" in text


@pytest.mark.parametrize(
    ("unknown", "project_unknown", "expected"),
    [
        (None, None, "fail"),
        ("warn", None, "warn"),
        ("warn", "fail", "fail"),
        ("warn", "warn", "warn"),
    ],
)
def test_unknown_paths_mode_survives_merge_and_fail_wins(
    tmp_path: Path, unknown, project_unknown, expected
):
    from loopspec.workflow_assurance import live_rules

    _, loaded = fixture(tmp_path, unknown=unknown, project_unknown=project_unknown)
    assert live_rules(loaded).unknown_paths == expected


def test_unknown_paths_rejects_other_values():
    from pydantic import ValidationError

    from loopspec.workflow_models import AssuranceRules

    rule = {"id": "x", "paths": ["x/**"], "requires": ["pr-review"], "repair_fragment": "x"}
    assert AssuranceRules.model_validate({"unknown_paths": "warn", "rules": [rule]})
    with pytest.raises(ValidationError):
        AssuranceRules.model_validate({"unknown_paths": "ignore", "rules": [rule]})


def test_warn_mode_passes_with_unknown_path_warning(tmp_path: Path):
    _, loaded = fixture(tmp_path, unknown="warn")
    (tmp_path / "frontend/code.py").write_text("implementation")
    (tmp_path / "unknown.py").write_text("unmatched change")
    review(loaded, "fe")
    qa(loaded)
    result = check(loaded)
    assert result["verdict"] == "PASS"
    assert result["unknown_paths"] == ["unknown.py"]
    assert result["warnings"] == {"unknownPaths": ["unknown.py"], "unknownTotal": 1}
    report = (loaded.root / "artifacts/assurance/p.md").read_text()
    assert "1 条告警" in report and "unknown.py" in report and "没有匹配任何保障规则" in report
    assert status(loaded)["isComplete"]


def test_warn_mode_still_fails_on_other_gaps(tmp_path: Path):
    _, loaded = fixture(tmp_path, unknown="warn")
    (tmp_path / "frontend/code.py").write_text("implementation")
    (tmp_path / "backend/code.py").write_text("backend edit no Gate covers")
    (tmp_path / "unknown.py").write_text("unmatched change")
    review(loaded, "fe")
    qa(loaded)
    result = check(loaded)
    assert result["verdict"] == "FAIL"
    assert result["missing_fragments"]
    assert "unknown.py" in (loaded.root / "artifacts/assurance/f.md").read_text()
    assert status(loaded)["nodes"][-1]["status"] in {"failed", "exhausted"}


def test_fail_mode_has_no_unknown_warning(tmp_path: Path):
    _, loaded = fixture(tmp_path)
    (tmp_path / "unknown.py").write_text("unmatched change")
    result = diagnose(loaded)
    assert not result["passed"]
    assert result["unknown_paths"] == ["unknown.py"]
    assert result["warnings"] is None


def test_unknown_warning_list_is_capped(tmp_path: Path):
    _, loaded = fixture(tmp_path, unknown="warn")
    names = [f"u{index:02d}.py" for index in range(25)]
    for name in reversed(names):
        (tmp_path / name).write_text(name)
    result = diagnose(loaded)
    assert result["unknown_paths"] == names
    assert result["warnings"] == {"unknownPaths": names[:20], "unknownTotal": 25}


def test_combined_long_warnings_keep_failure_summary_within_limit():
    from loopspec.workflow_assurance import warning_text
    from loopspec.workflow_models import FailureReport

    long = [f"{index:02d}/" + "d" * 4000 for index in range(20)]
    text = warning_text(
        {
            "ignoredPaths": long,
            "ignoredTotal": 30,
            "unknownPaths": [path + ".py" for path in long],
            "unknownTotal": 40,
        }
    )
    summary = "全量 Diff 保障存在缺口，请按诊断补齐审查或修订 Plan" + text
    FailureReport.model_validate({"verdict": "FAIL", "summary": summary})
    assert "30 条告警" in text and "40 条告警" in text


def test_committing_after_gates_keeps_change_complete_and_archivable(tmp_path: Path):
    home, loaded = fixture(tmp_path)
    (tmp_path / "frontend/code.py").write_text("implementation")
    review(loaded, "fe")
    qa(loaded)
    assert check(loaded)["verdict"] == "PASS"
    git(tmp_path, ["add", "-A"])
    git(tmp_path, ["commit", "-q", "-m", "deliver reviewed change"])
    assert status(loaded)["isComplete"]
    assert invoke(home, "change", "archive", "AFD1111", "--dry-run")[0] == 0


def test_committing_during_review_round_still_records(tmp_path: Path):
    _, loaded = fixture(tmp_path)
    (tmp_path / "frontend/code.py").write_text("implementation")
    atomic_write(loaded.root, "artifacts/fe/implementation.md", "实施结果".encode())
    context = begin(loaded.home, "AFD1111", "fe/review")
    assert "index" in context["paths"][0]
    git(tmp_path, ["add", "frontend/code.py"])
    git(tmp_path, ["commit", "-q", "-m", "commit mid review"])
    atomic_write(loaded.root, "artifacts/draft.md", b"verdict: PASS\nsummary: actual review\n")
    result = record(loaded.home, "AFD1111", "fe/review", context["roundId"], "artifacts/draft.md")
    assert result["evidenceRecorded"]
