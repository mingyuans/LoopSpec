from pathlib import Path

import pytest

from loopspec.errors import WorkflowError
from loopspec.workflow_catalog import WorkflowCatalog


def fragment_path(home: Path, name: str) -> Path:
    """Return ``fragments/<name>/fragment.yaml`` with its directory created."""
    directory = home / "fragments" / name
    directory.mkdir(parents=True, exist_ok=True)
    return directory / "fragment.yaml"


def test_catalog_single_read_and_local_override(tmp_path: Path):
    path = fragment_path(tmp_path, "one")
    path.write_text("name: one\nnodes:\n  - id: write\n    generates: one.md\n")
    catalog = WorkflowCatalog(tmp_path)
    assert catalog.entries("fragments")[0].name == "one"
    path.write_text("name: different\nnodes: []\n")
    assert catalog.fragment("one").nodes[0].id == "write"
    with pytest.raises(WorkflowError):
        WorkflowCatalog(tmp_path).fragment("one")


def test_catalog_lists_only_fragment_directories(tmp_path: Path):
    fragment_path(tmp_path, "one").write_text("name: one\nnodes:\n  - id: a\n    generates: a.md\n")
    (tmp_path / "fragments/flat.yaml").write_text("name: flat\nnodes: []\n")
    (tmp_path / "fragments/README.md").write_text("说明")
    (tmp_path / "fragments/empty").mkdir()
    catalog = WorkflowCatalog(tmp_path)
    assert [item.name for item in catalog.entries("fragments")] == ["one"]
    with pytest.raises(WorkflowError):
        catalog.fragment("flat")


def test_catalog_rejects_name_not_matching_directory(tmp_path: Path):
    fragment_path(tmp_path, "one").write_text("name: two\nnodes:\n  - id: a\n    generates: a.md\n")
    with pytest.raises(WorkflowError, match="名称与目录名不一致"):
        WorkflowCatalog(tmp_path).fragment("one")


def test_catalog_resolves_resource_inside_own_directory(tmp_path: Path):
    fragment_path(tmp_path, "one")
    (tmp_path / "fragments/one/write.instruction.md").write_text("写")
    assert (
        WorkflowCatalog(tmp_path).resource("one", "write.instruction.md")
        == "fragments/one/write.instruction.md"
    )


@pytest.mark.parametrize("path", ["../secret", "../two/write.instruction.md", "/etc/passwd"])
def test_catalog_refuses_escaping_resource(tmp_path: Path, path: str):
    fragment_path(tmp_path, "one")
    fragment_path(tmp_path, "two")
    (tmp_path / "fragments/two/write.instruction.md").write_text("写")
    with pytest.raises(WorkflowError) as error:
        WorkflowCatalog(tmp_path).resource("one", path)
    assert error.value.code == "unsafe_path"


def test_catalog_refuses_symlink_definition(tmp_path: Path):
    (tmp_path / "outside").write_text("name: one")
    fragment_path(tmp_path, "one").symlink_to(tmp_path / "outside")
    with pytest.raises(WorkflowError):
        WorkflowCatalog(tmp_path).entries("fragments")


def test_catalog_refuses_symlink_fragment_directory(tmp_path: Path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "fragment.yaml").write_text("name: one\nnodes:\n  - id: a\n    generates: a.md\n")
    (tmp_path / "fragments").mkdir()
    (tmp_path / "fragments/one").symlink_to(outside, target_is_directory=True)
    with pytest.raises(WorkflowError):
        WorkflowCatalog(tmp_path).entries("fragments")
    with pytest.raises(WorkflowError):
        WorkflowCatalog(tmp_path).fragment("one")
