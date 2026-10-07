"""Full-diff assurance: rule requirements are unioned; evidence binds to real paths and Gates."""

from __future__ import annotations

import fnmatch
from typing import Literal

from .errors import WorkflowError
from .workflow_diff import DiffSnapshot, collect_diff
from .workflow_evidence import Evidence, evidence_path, next_round, rounds_dir, valid_evidence
from .workflow_io import (
    ResourceBundle,
    archive_file,
    atomic_write,
    byte_hash,
    canonical,
    exists,
    write_json,
)
from .workflow_models import AssuranceRules, ResolvedNode
from .workflow_planning import assurance_rules, project_constraints
from .workflow_state import LoadedPlan


def live_rules(loaded: LoadedPlan) -> AssuranceRules:
    rules = assurance_rules(
        ResourceBundle(loaded.home), loaded.spec.nodes, project_constraints(loaded.home)
    )
    if rules is None:
        raise WorkflowError("assurance_missing", "Plan 与项目都没有配置保障规则")
    return rules


def diagnose(loaded: LoadedPlan, snapshot: DiffSnapshot | None = None) -> dict:
    snapshot = snapshot or collect_diff(loaded)
    rules = live_rules(loaded)
    providers = [node for node in loaded.spec.nodes if node.gate and node.gate.evidence]
    validity = {}
    for node in providers:
        assert node.gate
        validity[node.id] = (
            valid_evidence(loaded, node, snapshot=snapshot)
            if exists(loaded.root, node.gate.outputs.pass_)
            else (False, "evidence_missing")
        )
    result: dict = {
        "diffDigest": snapshot.diff_digest,
        "baseline": snapshot.baseline,
        "unknown_paths": [],
        "missing_evidence": [],
        "stale_evidence": [],
        "missing_fragments": [],
        "requiredCapabilities": {},
    }
    for entry in snapshot.entries:
        path = entry["path"]
        matches = [
            rule
            for rule in rules.rules
            if any(fnmatch.fnmatchcase(path, pattern) for pattern in rule.paths)
        ]
        if not matches:
            result["unknown_paths"].append(path)
            continue
        required = sorted({capability for rule in matches for capability in rule.requires})
        result["requiredCapabilities"][path] = required
        for capability in required:
            candidates = [
                node
                for node in providers
                if node.gate
                and node.gate.evidence
                and capability in node.gate.evidence.provides
                and any(fnmatch.fnmatchcase(path, pattern) for pattern in node.gate.evidence.paths)
            ]
            if any(validity[node.id][0] for node in candidates):
                continue
            if not candidates:
                repairs = sorted(
                    {rule.repair_fragment for rule in matches if capability in rule.requires}
                )
                result["missing_fragments"].append(
                    {"path": path, "capability": capability, "fragments": repairs}
                )
            else:
                category = (
                    "stale_evidence"
                    if any(validity[node.id][1] == "evidence_stale" for node in candidates)
                    else "missing_evidence"
                )
                result[category].append(
                    {
                        "path": path,
                        "capability": capability,
                        "gates": sorted(node.id for node in candidates),
                    }
                )
    result["passed"] = not any(
        result[category]
        for category in ("unknown_paths", "missing_evidence", "stale_evidence", "missing_fragments")
    )
    return result


def check(loaded: LoadedPlan, node: ResolvedNode) -> dict:
    """Run under the caller's write lock; only the system writes the assurance PASS/FAIL."""
    from .workflow_runtime import status

    assert node.gate
    entry = next(item for item in status(loaded)["nodes"] if item["id"] == node.id)
    root = loaded.root
    snapshot = collect_diff(loaded)
    diagnostics = diagnose(loaded, snapshot)
    if entry["status"] == "blocked":
        return {**diagnostics, "recorded": False, "blockedBy": entry.get("missingDeps", [])}
    verdict: Literal["PASS", "FAIL"] = "PASS" if diagnostics["passed"] else "FAIL"
    # The report holds only the deterministic verdict; diagnostics are stored separately.
    report = (
        canonical(
            {
                "verdict": verdict,
                "summary": "全量 Diff 保障通过"
                if verdict == "PASS"
                else "全量 Diff 保障存在缺口，请按诊断补齐审查或修订 Plan",
            }
        )
        + b"\n"
    )
    round_number = next_round(root, node.id)
    for output in (node.gate.outputs.pass_, node.gate.outputs.fail):
        if exists(root, output):
            archive_file(root, output, f"{rounds_dir(node.id)}/prior/{round_number:03d}/" + output)
    output = node.gate.outputs.pass_ if verdict == "PASS" else node.gate.outputs.fail
    atomic_write(root, output, report)
    if collect_diff(loaded).diff_digest != snapshot.diff_digest:
        raise WorkflowError("concurrent_input_change", "保障记录期间输入变化，未产生有效证据")
    evidence = Evidence(
        gate=node.id,
        plan_digest=loaded.digest,
        baseline=snapshot.baseline,
        round=round_number,
        verdict=verdict,
        paths=["**"],
        provides=[],
        scope_digest=snapshot.diff_digest,
        report_hash=byte_hash(report),
        system=True,
    )
    write_json(
        root,
        f"{rounds_dir(node.id)}/{round_number:03d}.yaml",
        evidence.model_dump(),
        exclusive=True,
    )
    write_json(root, f".gates/{node.id}/assurance.yaml", diagnostics)
    write_json(root, evidence_path(node.id), evidence.model_dump())
    return {**diagnostics, "gate": node.id, "verdict": verdict, "recorded": True}
