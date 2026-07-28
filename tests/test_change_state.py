from pathlib import Path

from loopspec.change_state import create_initial_state, read_state_for_instruction


def test_create_initial_state_contains_all_sections(tmp_path: Path):
    path = create_initial_state(tmp_path)
    text = path.read_text()
    for section in (
        "Current Focus",
        "Frozen Decisions",
        "Decision Log",
        "Rejected Options",
        "Open Questions",
        "Artifact Notes",
    ):
        assert section in text


def test_read_existing_state_no_warnings(tmp_path: Path):
    create_initial_state(tmp_path)
    text, warnings = read_state_for_instruction(tmp_path)
    assert text is not None
    assert warnings == []


def test_read_missing_state_returns_warning(tmp_path: Path):
    text, warnings = read_state_for_instruction(tmp_path)
    assert text is None
    assert warnings == ["state_missing"]


def test_semantic_tags_returned_verbatim(tmp_path: Path):
    (tmp_path / "state.md").write_text("## Artifact Notes\n- proposal.md: [approved]\n")
    text, _ = read_state_for_instruction(tmp_path)
    assert "[approved]" in text


def test_contradiction_with_artifacts_does_not_raise(tmp_path: Path):
    # state.md claims a file is approved even though it doesn't exist on disk;
    # reading state.md never inspects the filesystem, so this is not an error.
    (tmp_path / "state.md").write_text("- proposal.md: approved\n")
    text, warnings = read_state_for_instruction(tmp_path)
    assert text is not None
    assert warnings == []
