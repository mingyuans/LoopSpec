from pathlib import Path

import pytest
import yaml

from loopspec.errors import WorkflowError
from loopspec.workflow_catalog import WorkflowCatalog
from loopspec.workflow_models import PlanRequest, Profile, ProjectWorkflow
from loopspec.workflow_planning import (
    check_constraints,
    compile_flow,
    compile_request,
    load_request,
    project_constraints,
    validate_profile,
)
from tests.test_workflow_catalog import fragment_path


def setup_catalog(home: Path):
    for name, node in {
        "implementation": {"id": "code", "generates": "code.md"},
        "testing": {"id": "test", "gate": {"outputs": {"pass": "p.md", "fail": "f.md"}}},
    }.items():
        fragment_path(home, name).write_text(yaml.safe_dump({"name": name, "nodes": [node]}))
    return WorkflowCatalog(home)


def example_profile():
    return {
        "name": "fullstack",
        "flow": [
            {"id": "fe", "use": "implementation"},
            {"id": "be", "use": "implementation"},
            {
                "id": "qa",
                "use": "testing",
                "requires": ["fe", "be"],
                "on_fail": {"reset": ["be", "fe"], "max_retries": 3},
            },
        ],
    }


def test_parallel_profile_and_flow_on_fail(tmp_path: Path):
    result = validate_profile(setup_catalog(tmp_path), Profile.model_validate(example_profile()))
    assert result["buildOrder"] == ["be/code", "fe/code", "qa/test"]
    assert result["onFail"] == {"qa/test": {"reset": ["be/code", "fe/code"], "max_retries": 3}}


@pytest.mark.parametrize("field", ["recovery", "cases", "protected", "min_engine_version"])
def test_profile_and_request_reject_removed_fields(field):
    value = example_profile()
    value[field] = [{"from": "qa/test", "cases": {"backend": ["be"]}}]
    with pytest.raises(ValueError):
        Profile.model_validate(value)
    with pytest.raises(ValueError):
        PlanRequest.model_validate({"flow": value["flow"], field: value[field]})


@pytest.mark.parametrize("field", ["reasons", "deviations", "baseline", "version"])
def test_request_rejects_removed_fields(field):
    with pytest.raises(ValueError):
        PlanRequest.model_validate({"flow": example_profile()["flow"], field: {"fe": "x"}})


@pytest.mark.parametrize(
    "mutation", ["duplicate", "missing", "cycle", "downstream", "self", "unknown"]
)
def test_invalid_profile(tmp_path: Path, mutation):
    value = example_profile()
    if mutation == "duplicate":
        value["flow"][1]["id"] = "fe"
    elif mutation == "missing":
        value["flow"][0]["requires"] = ["unknown"]
    elif mutation == "cycle":
        value["flow"][0]["requires"] = ["qa"]
    elif mutation == "downstream":
        value["flow"][0]["on_fail"] = {"reset": ["qa"]}
    elif mutation == "self":
        value["flow"][2]["on_fail"] = {"reset": ["qa"]}
    else:
        value["flow"][2]["on_fail"] = {"reset": ["missing"]}
    with pytest.raises(WorkflowError):
        validate_profile(setup_catalog(tmp_path), Profile.model_validate(value))


def test_flow_on_fail_on_top_of_inner_on_fail_is_a_conflict(tmp_path: Path):
    catalog = setup_catalog(tmp_path)
    fragment_path(tmp_path, "checked").write_text(
        yaml.safe_dump(
            {
                "name": "checked",
                "nodes": [
                    {"id": "code", "generates": "code.md"},
                    {
                        "id": "test",
                        "requires": ["code"],
                        "gate": {"outputs": {"pass": "p.md", "fail": "f.md"}},
                        "on_fail": {"reset": ["code"]},
                    },
                ],
            }
        )
    )
    flow = Profile.model_validate(
        {
            "name": "x",
            "flow": [
                {"id": "fe", "use": "implementation"},
                {"id": "be", "use": "checked", "requires": ["fe"], "on_fail": {"reset": ["fe"]}},
            ],
        }
    ).flow
    with pytest.raises(WorkflowError) as error:
        compile_flow(catalog, flow)
    assert error.value.code == "on_fail_conflict"


def test_project_rules_cannot_disappear_with_light_profile(tmp_path: Path):
    catalog = setup_catalog(tmp_path)
    profile = Profile.model_validate(example_profile())
    expanded = compile_flow(catalog, profile.flow)
    with pytest.raises(WorkflowError, match="项目要求"):
        check_constraints(ProjectWorkflow(required_fragments=["mandatory"]), expanded)
    with pytest.raises(WorkflowError, match="保障节点"):
        check_constraints(ProjectWorkflow(assurance_rules="rules/code.yaml"), expanded)


@pytest.mark.parametrize(
    "config",
    [
        "schema: secure-spec-driven\n",
        "schemas: []\n",
        "context: x\n",
        "rules: {}\n",
        "schema_selection: {instruction: x}\n",
        "workflow:\n  default_profile: bugfix\n",
    ],
)
def test_config_rejects_removed_fields(tmp_path: Path, config):
    (tmp_path / "config.yaml").write_text(config)
    with pytest.raises(WorkflowError) as error:
        project_constraints(tmp_path)
    assert error.value.code == "config_invalid"


def test_generated_dirs_cannot_name_business_directories(tmp_path: Path):
    (tmp_path / "config.yaml").write_text("workflow:\n  generated_dirs: [backend]\n")
    with pytest.raises(WorkflowError, match="业务目录"):
        project_constraints(tmp_path)


def test_spec_holds_only_based_on_flow_and_nodes(tmp_path: Path):
    setup_catalog(tmp_path)
    (tmp_path / "config.yaml").write_text("workflow: {}\n")
    (tmp_path / "request.yaml").write_text(
        yaml.safe_dump({"flow": [{"id": "fe", "use": "implementation"}]})
    )
    compiled = compile_request(tmp_path, load_request(tmp_path, "request.yaml"))
    assert set(compiled.result()["spec"]) == {"flow", "nodes"}
    assert compiled.spec.nodes[0].id == "fe/code"


def test_digest_binds_graph_not_resource_bytes(tmp_path: Path):
    setup_catalog(tmp_path)
    (tmp_path / "config.yaml").write_text("workflow: {}\n")
    (tmp_path / "fragments/implementation/code.instruction.md").write_text("first")
    fragment_path(tmp_path, "implementation").write_text(
        yaml.safe_dump(
            {
                "name": "implementation",
                "nodes": [
                    {"id": "code", "generates": "code.md", "instruction": "code.instruction.md"}
                ],
            }
        )
    )
    request = PlanRequest.model_validate({"flow": [{"id": "fe", "use": "implementation"}]})
    first = compile_request(tmp_path, request)
    (tmp_path / "fragments/implementation/code.instruction.md").write_text("second")
    assert compile_request(tmp_path, request).digest == first.digest
    fragment_path(tmp_path, "implementation").write_text(
        yaml.safe_dump({"name": "implementation", "nodes": [{"id": "code", "generates": "x.md"}]})
    )
    assert compile_request(tmp_path, request).digest != first.digest
