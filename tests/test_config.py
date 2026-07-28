from pathlib import Path

import pytest

from loopspec.config import (
    load_config,
    read_metadata,
    resolve_schema_for_existing_change,
    resolve_schema_for_new_change,
    schema_path_for,
    write_metadata,
)
from loopspec.errors import ConfigValidationError, SchemaSelectionRequiredError
from loopspec.paths import artifact_root, artifacts_root, change_root


def make_builtin_schema(workflow_home: Path, name: str) -> None:
    schema_dir = workflow_home / "schemas" / name
    schema_dir.mkdir(parents=True)
    (schema_dir / "schema.yaml").write_text("name: " + name + "\nversion: 1\nnodes: []\n")


def write_config(workflow_home: Path, text: str) -> None:
    workflow_home.mkdir(parents=True, exist_ok=True)
    (workflow_home / "config.yaml").write_text(text, encoding="utf-8")


def test_single_default_schema_loads(tmp_path: Path):
    make_builtin_schema(tmp_path, "spec-driven")
    write_config(tmp_path, "schema: spec-driven\n")
    config = load_config(tmp_path)
    assert config.schema_name == "spec-driven"
    assert config.artifacts_dir == "changes"


def test_custom_artifacts_dir_resolves(tmp_path: Path):
    make_builtin_schema(tmp_path, "spec-driven")
    write_config(tmp_path, "schema: spec-driven\nartifacts_dir: artifacts\n")
    config = load_config(tmp_path)
    root = artifacts_root(tmp_path, config.artifacts_dir)
    assert root == (tmp_path / "artifacts").resolve()


def test_multiple_candidates_preserved(tmp_path: Path):
    for name in ("secure-spec-driven", "docs-only", "bugfix"):
        make_builtin_schema(tmp_path, name)
    write_config(
        tmp_path,
        """
schemas:
  - name: secure-spec-driven
    description: default
    when: general
  - name: docs-only
    path: docs
    description: docs
    when: docs only
  - name: bugfix
    path: bugfix
    description: bugfix
    when: fixing bugs
schema_selection:
  instruction: pick the best match
""",
    )
    config = load_config(tmp_path)
    assert [ref.name for ref in config.schemas] == ["secure-spec-driven", "docs-only", "bugfix"]
    assert config.schema_selection is not None
    assert schema_path_for(config, "docs-only") == "docs"


def test_schema_path_resolves_artifact_root(tmp_path: Path):
    change_dir = tmp_path / "changes" / "fix-login"
    change_dir.mkdir(parents=True)
    root = artifact_root(change_dir, "bugfix")
    assert root == (change_dir / "bugfix").resolve()


def test_schema_and_schemas_consistent_loads(tmp_path: Path):
    make_builtin_schema(tmp_path, "a")
    make_builtin_schema(tmp_path, "b")
    write_config(
        tmp_path,
        """
schema: a
schemas:
  - name: a
  - name: b
""",
    )
    config = load_config(tmp_path)
    assert config.schema_name == "a"


def test_default_schema_not_in_candidates_rejected(tmp_path: Path):
    make_builtin_schema(tmp_path, "a")
    write_config(tmp_path, "schema: z\nschemas:\n  - name: a\n")
    with pytest.raises(ConfigValidationError):
        load_config(tmp_path)


def test_duplicate_candidate_names_rejected(tmp_path: Path):
    make_builtin_schema(tmp_path, "a")
    write_config(tmp_path, "schemas:\n  - name: a\n  - name: a\n")
    with pytest.raises(ConfigValidationError):
        load_config(tmp_path)


def test_absolute_artifacts_dir_rejected(tmp_path: Path):
    make_builtin_schema(tmp_path, "a")
    write_config(tmp_path, "schema: a\nartifacts_dir: /etc/changes\n")
    with pytest.raises(ConfigValidationError):
        load_config(tmp_path)


def test_traversal_in_schema_path_rejected(tmp_path: Path):
    make_builtin_schema(tmp_path, "a")
    write_config(tmp_path, "schemas:\n  - name: a\n    path: '../escape'\n")
    with pytest.raises(ConfigValidationError):
        load_config(tmp_path)


def test_neither_schema_nor_schemas_rejected(tmp_path: Path):
    write_config(tmp_path, "artifacts_dir: changes\n")
    with pytest.raises(ConfigValidationError):
        load_config(tmp_path)


def test_unloadable_candidate_schema_rejected(tmp_path: Path):
    write_config(tmp_path, "schemas:\n  - name: missing-schema\n")
    with pytest.raises(ConfigValidationError):
        load_config(tmp_path)


def test_multi_candidate_without_selection_instruction_still_loads(tmp_path: Path):
    make_builtin_schema(tmp_path, "a")
    make_builtin_schema(tmp_path, "b")
    write_config(tmp_path, "schemas:\n  - name: a\n  - name: b\n")
    config = load_config(tmp_path)
    assert config.schema_selection is None


def test_resolve_schema_for_new_change_single_candidate(tmp_path: Path):
    make_builtin_schema(tmp_path, "a")
    write_config(tmp_path, "schemas:\n  - name: a\n")
    config = load_config(tmp_path)
    assert resolve_schema_for_new_change(config, None) == "a"


def test_resolve_schema_for_new_change_multi_candidate_requires_selection(tmp_path: Path):
    make_builtin_schema(tmp_path, "a")
    make_builtin_schema(tmp_path, "b")
    write_config(tmp_path, "schemas:\n  - name: a\n  - name: b\n")
    config = load_config(tmp_path)
    with pytest.raises(SchemaSelectionRequiredError):
        resolve_schema_for_new_change(config, None)
    assert resolve_schema_for_new_change(config, "b") == "b"


def test_resolve_schema_for_new_change_rejects_schema_not_in_candidates(tmp_path: Path):
    make_builtin_schema(tmp_path, "a")
    make_builtin_schema(tmp_path, "b")
    write_config(tmp_path, "schemas:\n  - name: a\n  - name: b\n")
    config = load_config(tmp_path)
    with pytest.raises(ConfigValidationError):
        resolve_schema_for_new_change(config, "not-a-candidate")


def test_resolve_schema_for_existing_change_priority_order(tmp_path: Path):
    make_builtin_schema(tmp_path, "a")
    write_config(tmp_path, "schema: a\n")
    config = load_config(tmp_path)

    assert resolve_schema_for_existing_change(config, None, "explicit") == "explicit"
    from loopspec.models import WorkflowMetadata

    meta = WorkflowMetadata(schema="from-metadata", created="2026-01-01")
    assert resolve_schema_for_existing_change(config, meta, None) == "from-metadata"
    assert resolve_schema_for_existing_change(config, None, None) == "a"


def test_write_and_read_metadata_roundtrip(tmp_path: Path):
    change_dir = tmp_path / "add-payment"
    change_dir.mkdir()
    write_metadata(change_dir, "secure-spec-driven", "2026-07-27")

    metadata = read_metadata(change_dir)
    assert metadata is not None
    assert metadata.schema_name == "secure-spec-driven"
    assert metadata.created == "2026-07-27"


def test_read_metadata_missing_returns_none(tmp_path: Path):
    assert read_metadata(tmp_path) is None


def test_change_root_resolution(tmp_path: Path):
    root = change_root(tmp_path, "changes", "add-payment")
    assert root == (tmp_path / "changes" / "add-payment").resolve()
