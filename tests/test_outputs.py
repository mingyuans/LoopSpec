from pathlib import Path

from loopspec.models import NodeSpec
from loopspec.outputs import is_glob, node_output_patterns, outputs_exist, resolve_outputs


def test_is_glob_detects_wildcard_characters():
    assert is_glob("specs/**/*.md")
    assert is_glob("a?.md")
    assert is_glob("[abc].md")
    assert not is_glob("design.md")


def test_glob_node_matches_multiple_files(tmp_path: Path):
    (tmp_path / "specs" / "foo").mkdir(parents=True)
    (tmp_path / "specs" / "foo" / "spec.md").write_text("x")
    (tmp_path / "specs" / "bar").mkdir(parents=True)
    (tmp_path / "specs" / "bar" / "spec.md").write_text("y")

    matches = resolve_outputs(tmp_path, "specs/**/*.md")
    assert len(matches) == 2
    assert matches == sorted(matches)
    assert outputs_exist(tmp_path, "specs/**/*.md")


def test_glob_node_no_match(tmp_path: Path):
    assert resolve_outputs(tmp_path, "specs/**/*.md") == []
    assert not outputs_exist(tmp_path, "specs/**/*.md")


def test_attempts_directory_excluded_from_glob(tmp_path: Path):
    (tmp_path / ".attempts" / "round-001").mkdir(parents=True)
    (tmp_path / ".attempts" / "round-001" / "design.md").write_text("archived")

    assert resolve_outputs(tmp_path, "**/*.md") == []


def test_state_md_excluded_from_glob(tmp_path: Path):
    (tmp_path / "state.md").write_text("# state")

    assert resolve_outputs(tmp_path, "**/*.md") == []


def test_workflow_yaml_excluded_from_glob(tmp_path: Path):
    (tmp_path / ".workflow.yaml").write_text("schema: x")

    assert resolve_outputs(tmp_path, "**/*") == []


def test_non_glob_output_exists(tmp_path: Path):
    (tmp_path / "proposal.md").write_text("x")
    assert outputs_exist(tmp_path, "proposal.md")
    assert not outputs_exist(tmp_path, "design.md")


def test_node_output_patterns_for_plain_node():
    node = NodeSpec(id="design", description="d", generates="design.md", template="design.md")
    assert node_output_patterns(node) == ["design.md"]


def test_node_output_patterns_for_gate_node():
    node = NodeSpec(
        id="security",
        description="s",
        generates=None,
        template=None,
        gate={
            "outputs": {"pass": "security/pass.md", "fail": "security/fail.md"},
            "templates": {"pass": "security-pass.md", "fail": "security-fail.md"},
            "on_fail": {"reset": ["design"]},
        },
    )
    assert node_output_patterns(node) == ["security/pass.md", "security/fail.md"]
