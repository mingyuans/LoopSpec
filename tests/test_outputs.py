from pathlib import Path

from loopspec.models import NodeSpec
from loopspec.outputs import (
    is_glob,
    node_output_patterns,
    outputs_exist,
    resolve_outputs,
    resolved_output_path,
)


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


def test_resolved_output_path_of_a_concrete_path_is_that_path(tmp_path: Path):
    """Answered before the file exists: it is where the artifact goes."""

    assert resolved_output_path(tmp_path, "proposal.md") == str(tmp_path / "proposal.md")
    (tmp_path / "proposal.md").write_text("x")
    assert resolved_output_path(tmp_path, "proposal.md") == str(tmp_path / "proposal.md")


def test_resolved_output_path_of_a_glob_lists_the_matches(tmp_path: Path):
    """Never a path with a wildcard in it -- those are not paths."""

    (tmp_path / "specs").mkdir()
    (tmp_path / "specs" / "b.md").write_text("b")
    (tmp_path / "specs" / "a.md").write_text("a")

    resolved = resolved_output_path(tmp_path, "specs/**/*.md")
    assert resolved == [str(tmp_path / "specs" / "a.md"), str(tmp_path / "specs" / "b.md")]
    assert all("*" not in path for path in resolved)


def test_resolved_output_path_of_an_unmatched_glob_is_none(tmp_path: Path):
    """No file yet means there is no path to name, so say so rather than invent one."""

    (tmp_path / "specs").mkdir()
    assert resolved_output_path(tmp_path, "specs/**/*.md") is None


def test_resolved_output_path_of_a_glob_excludes_attempts_and_reserved_files(tmp_path: Path):
    """The same filtering resolve_outputs applies, so an archived attempt cannot
    surface as a current artifact."""

    (tmp_path / ".attempts" / "round-001").mkdir(parents=True)
    (tmp_path / ".attempts" / "round-001" / "old.md").write_text("old")
    (tmp_path / "state.md").write_text("state")
    assert resolved_output_path(tmp_path, "**/*.md") is None

    (tmp_path / "current.md").write_text("now")
    assert resolved_output_path(tmp_path, "**/*.md") == [str(tmp_path / "current.md")]


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
