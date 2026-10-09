from pathlib import Path

import pytest

from loopspec.builtin_resources import builtin_root
from loopspec.workflow_catalog import WorkflowCatalog
from loopspec.workflow_evidence import GateReport
from loopspec.workflow_io import atomic_write
from loopspec.workflow_models import FailureReport
from loopspec.workflow_yaml import parse_yaml
from tests.workflow_helpers import CHANGE, create_approved, invoke, project

FRAGMENTS = builtin_root() / "fragments"
CATALOG = WorkflowCatalog(builtin_root())
BUILTIN = CATALOG.entries("fragments")


def gate_templates():
    for fragment in BUILTIN:
        for node in fragment.nodes:
            if node.gate and node.gate.templates:
                for verdict, path in (
                    ("PASS", node.gate.templates.pass_),
                    ("FAIL", node.gate.templates.fail),
                ):
                    yield pytest.param(
                        fragment.name, verdict, path, id=f"{fragment.name}/{node.id}/{verdict}"
                    )


def front_matter(text: str) -> dict:
    assert text.startswith("---\n"), "Gate 模板必须以 YAML 头部开始"
    head, separator, _ = text[4:].partition("\n---")
    assert separator, "Gate 模板 YAML 头部未闭合"
    return parse_yaml(head)


def test_builtin_fragments_are_self_contained_directories():
    names = sorted(path.name for path in FRAGMENTS.iterdir() if path.is_dir())
    assert names == sorted(fragment.name for fragment in BUILTIN)
    assert not list(FRAGMENTS.glob("*.yaml"))
    assert not (FRAGMENTS / "instructions").exists()
    assert not (FRAGMENTS / "templates").exists()
    assert not (FRAGMENTS / "rules").exists()


def test_builtin_fragment_resources_exist_and_cover_templates():
    for fragment in BUILTIN:
        for node in fragment.nodes:
            if node.use is not None:
                continue
            resources = [node.instruction, node.template]
            if node.generates:
                assert node.template, f"{fragment.name}/{node.id} 缺少产物模板"
            if node.gate and not node.gate.assurance:
                assert node.gate.templates, f"{fragment.name}/{node.id} 缺少 Gate 模板"
            if node.gate and node.gate.templates:
                resources += [node.gate.templates.pass_, node.gate.templates.fail]
            if node.gate and node.gate.assurance:
                resources.append(node.gate.assurance)
            for resource in filter(None, resources):
                assert CATALOG.resource(fragment.name, resource)


def test_builtin_fragments_do_not_share_resource_files():
    for fragment in BUILTIN:
        directory = FRAGMENTS / fragment.name
        listed = {path.name for path in directory.iterdir()} - {"fragment.yaml"}
        referenced = set()
        for node in fragment.nodes:
            referenced.update(filter(None, [node.instruction, node.template]))
            if node.gate and node.gate.templates:
                referenced.update([node.gate.templates.pass_, node.gate.templates.fail])
            if node.gate and node.gate.assurance:
                referenced.add(node.gate.assurance)
        assert listed == referenced, f"{fragment.name} 存在未引用或缺失的资源"


@pytest.mark.parametrize(("fragment", "verdict", "path"), list(gate_templates()))
def test_gate_template_front_matter_matches_report_contract(fragment, verdict, path):
    text = (FRAGMENTS / fragment / path).read_text(encoding="utf-8")
    head = front_matter(text)
    assert head["verdict"] == verdict
    assert set(head) == {"verdict", "summary"}
    GateReport.model_validate({**head, "summary": "已填写"})
    if verdict == "FAIL":
        FailureReport.model_validate({**head, "summary": "已填写"})


MANUAL_FLOW = [
    {"id": "requirements", "use": "requirements"},
    {"id": "design", "use": "design", "requires": ["requirements"]},
    {"id": "implementation", "use": "backend-code", "requires": ["design"]},
    {"id": "qa", "use": "qa-testing", "requires": ["implementation"]},
]


def test_plan_records_template_paths_not_bytes(tmp_path: Path):
    home = project(tmp_path, code=False)
    nodes = {node.id: node for node in create_approved(home, MANUAL_FLOW).spec.nodes}
    assert nodes["requirements/proposal"].template == "fragments/requirements/proposal.template.md"
    gate = nodes["qa/test"].gate
    assert gate and gate.templates
    assert gate.templates.pass_ == "fragments/qa-testing/test.pass.md"
    assert gate.templates.fail == "fragments/qa-testing/test.fail.md"


def test_artifact_node_returns_single_template(tmp_path: Path):
    home = project(tmp_path, code=False)
    create_approved(home, MANUAL_FLOW)
    code, result = invoke(home, "node", "instructions", "-c", CHANGE, "-n", "requirements/proposal")
    assert code == 0, result
    expected = (FRAGMENTS / "requirements/proposal.template.md").read_text(encoding="utf-8")
    assert result["template"] == expected
    assert "templates" not in result


def test_gate_node_returns_pass_and_fail_templates(tmp_path: Path):
    home = project(tmp_path, code=False)
    root = create_approved(home, MANUAL_FLOW).root
    for path in (
        "artifacts/requirements/proposal.md",
        "artifacts/design/design.md",
        "artifacts/design/tasks.md",
        "artifacts/implementation/implementation.md",
    ):
        atomic_write(root, path, "已完成".encode())
    code, result = invoke(home, "node", "instructions", "-c", CHANGE, "-n", "qa/test")
    assert code == 0, result
    assert result["templates"] == {
        "pass": (FRAGMENTS / "qa-testing/test.pass.md").read_text(encoding="utf-8"),
        "fail": (FRAGMENTS / "qa-testing/test.fail.md").read_text(encoding="utf-8"),
    }
    assert "template" not in result


def test_reports_reject_route_case():
    with pytest.raises(ValueError):
        GateReport.model_validate({"verdict": "FAIL", "summary": "x", "route_case": "backend"})
    with pytest.raises(ValueError):
        FailureReport.model_validate({"verdict": "FAIL", "summary": "x", "route_case": "backend"})


def test_builtin_profiles_use_flow_on_fail():
    expected = {
        "large-feature": ["fe", "be"],
        "frontend-small-change": ["fe"],
        "bugfix": ["be"],
    }
    for profile in CATALOG.entries("profiles"):
        assert "recovery" not in profile.model_fields_set
        if profile.name in expected:
            qa = next(entry for entry in profile.flow if entry.id == "qa")
            assert qa.on_fail is not None
            assert qa.on_fail.reset == expected[profile.name]
