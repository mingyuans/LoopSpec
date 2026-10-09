"""Workflow models reject unknown or removed fields by default."""

import pytest
from pydantic import ValidationError

from loopspec.workflow_models import (
    ChangeState,
    FailureReport,
    Fragment,
    Node,
    PlanDocument,
    PlanMeta,
    PlanRequest,
)
from loopspec.workflow_yaml import parse_yaml


def test_mixed_nodes():
    fragment = Fragment.model_validate(
        {
            "name": "mixed",
            "nodes": [
                {"id": "implement", "generates": "implementation.md"},
                {
                    "id": "security",
                    "use": "security-review",
                    "requires": ["implement"],
                    "on_fail": {"reset": ["implement"], "max_retries": 3},
                },
            ],
        }
    )
    assert fragment.nodes[1].use == "security-review"


@pytest.mark.parametrize(
    "value",
    [
        {"id": "a", "use": "b", "instruction": "run.md"},
        {"id": "a", "generates": "a.md", "on_fail": {"reset": ["b"]}},
        {"id": "../a", "use": "b"},
        {"id": "a", "use": "b", "command": "untrusted"},
    ],
)
def test_invalid_node(value):
    with pytest.raises(ValidationError):
        Node.model_validate(value)


def test_includes_and_duplicate_ids_rejected():
    for value in [
        {"name": "a", "nodes": [], "includes": []},
        {"name": "a", "nodes": [{"id": "b", "use": "c"}] * 2},
    ]:
        with pytest.raises(ValidationError):
            Fragment.model_validate(value)


def test_request_has_optional_profile():
    assert PlanRequest.model_validate({"flow": [{"id": "a", "use": "b"}]}).based_on is None


def test_blank_failure_summary_is_not_business_failure():
    with pytest.raises(ValidationError, match="不能为空白"):
        FailureReport.model_validate({"verdict": "FAIL", "summary": " \n\t"})


@pytest.mark.parametrize(
    "document",
    [
        "name: a\nname: b\n",
        "a: &anchor [b]\nc: *anchor\n",
        "a: !!python/object:builtins.object {}",
        "a: " + "[" * 65 + "]" * 65,
    ],
)
def test_yaml_rejects_duplicate_alias_object_depth(document):
    with pytest.raises(ValueError):
        parse_yaml(document)


META = {
    "plan": "002",
    "status": "approved",
    "revision": 1,
    "digest": "c" * 64,
    "approved_at": "2026-10-07T10:20:00+00:00",
    "note": None,
    "created": "2026-10-07T10:05:00+00:00",
    "archived_at": None,
    "archive_note": None,
}


def test_plan_meta_status_is_only_a_human_decision():
    assert PlanMeta.model_validate(META).status == "approved"
    for status in ("completed", "discarded", "suspended"):
        with pytest.raises(ValidationError):
            PlanMeta.model_validate({**META, "status": status})


@pytest.mark.parametrize(
    "change",
    [
        {"status": "draft"},
        {"revision": 0},
        {"approved_at": None},
        {"archived_at": "2026-10-07T11:00:00+00:00"},
        {"archive_note": "x"},
        {"plan": "2"},
        {"plan": "../1"},
    ],
)
def test_plan_meta_rejects_inconsistent_fields(change):
    with pytest.raises(ValidationError):
        PlanMeta.model_validate({**META, **change})


@pytest.mark.parametrize("field", ["approval", "history", "pending", "reason", "discarded_at"])
def test_plan_meta_rejects_removed_fields(field):
    with pytest.raises(ValidationError):
        PlanMeta.model_validate({**META, field: "x"})


SPEC = {
    "flow": [{"id": "fe", "use": "frontend-code"}],
    "nodes": [{"id": "fe/implement", "fragment": "fe", "generates": "artifacts/fe/x.md"}],
}


@pytest.mark.parametrize(
    "field",
    [
        "baseline",
        "repository",
        "engine_version",
        "instances",
        "project",
        "resources",
        "reasons",
        "recovery",
    ],
)
def test_plan_spec_rejects_removed_fields(field):
    with pytest.raises(ValidationError):
        PlanDocument.model_validate({"meta": META, "spec": {**SPEC, field: {}}})


def test_plan_spec_must_be_a_closed_graph():
    broken = {**SPEC, "nodes": [{**SPEC["nodes"][0], "requires": ["missing"]}]}
    with pytest.raises(ValidationError):
        PlanDocument.model_validate({"meta": META, "spec": broken})


def test_change_state_holds_no_plan_pointers():
    state = ChangeState(change_name="AFD1111", created="t")
    assert state.model_dump() == {
        "format_version": 4,
        "change_name": "AFD1111",
        "created": "t",
        "baseline": None,
        "repository": None,
    }
    for value in (
        {"active_plan": "001"},
        {"open_plan": "001"},
        {"next_plan": 2},
        {"baseline": "a" * 40},
        {"format_version": 3},
    ):
        with pytest.raises(ValidationError):
            ChangeState.model_validate({"change_name": "AFD1111", "created": "t", **value})
