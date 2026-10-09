import pytest

from loopspec.builtin_resources import builtin_root
from loopspec.workflow_catalog import WorkflowCatalog
from loopspec.workflow_planning import validate_profile

ON_FAIL = {
    "bugfix": {
        "qa/test": ["be/code/implement", "be/review/check", "be/security/check", "be/tests/check"]
    },
    "frontend-small-change": {
        "qa/test": ["fe/code/implement", "fe/review/check", "fe/tests/check"]
    },
}


@pytest.mark.parametrize("name", ["large-feature", "frontend-small-change", "bugfix"])
def test_builtin_profiles_compile_without_conflict(name: str):
    catalog = WorkflowCatalog(builtin_root())
    result = validate_profile(catalog, catalog.profile(name))
    assert result["valid"]
    assert result["buildOrder"]
    for gate, reset in ON_FAIL.get(name, {}).items():
        assert result["onFail"][gate]["reset"] == reset


def test_builtin_catalog_has_no_removed_capabilities():
    catalog = WorkflowCatalog(builtin_root())
    assert {item.name for item in catalog.entries("profiles")} == {
        "bugfix",
        "frontend-small-change",
        "large-feature",
    }
    assert "delivery-review" not in {item.name for item in catalog.entries("fragments")}
    for path in (builtin_root() / "fragments").glob("*/fragment.yaml"):
        assert "min_engine_version" not in path.read_text()
    for path in (builtin_root() / "profiles").glob("*.yaml"):
        assert "min_engine_version" not in path.read_text()
        assert "protected" not in path.read_text()


def test_bugfix_profile_matches_design_example():
    catalog = WorkflowCatalog(builtin_root())
    result = validate_profile(catalog, catalog.profile("bugfix"))
    for gate in ("be/tests/check", "be/security/check", "be/review/check"):
        assert result["onFail"][gate] == {"reset": ["be/code/implement"], "max_retries": 3}
