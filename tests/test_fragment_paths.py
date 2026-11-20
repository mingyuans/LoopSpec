"""`node instructions` names the node's Fragment and its absolute directory and files."""

from __future__ import annotations

from pathlib import Path

from loopspec import registry_store
from tests.registry_helpers import registry_project, sync
from tests.workflow_helpers import (
    BUGFIX_FLOW,
    CHANGE,
    create_approved,
    invoke,
    project,
    run_until,
)


def instructions(home: Path, node: str) -> dict:
    code, data = invoke(home, "node", "instructions", "-c", CHANGE, "-n", node)
    assert code == 0, data
    return data


def test_local_fragment_paths(tmp_path: Path) -> None:
    home = project(tmp_path)
    create_approved(home, BUGFIX_FLOW)
    data = instructions(home, "requirements/proposal")
    assert data["fragment"] == "requirements"  # the instance id, unchanged
    assert data["fragmentName"] == "requirements"
    assert data["fragmentDir"] == str(home.resolve() / "fragments" / "requirements")
    assert Path(data["instructionPath"]).read_text() == data["instruction"]
    assert Path(data["templatePath"]).read_text() == data["template"]
    assert Path(data["instructionPath"]).parent == Path(data["fragmentDir"])


def test_nested_fragment_names_the_defining_fragment(tmp_path: Path) -> None:
    home = project(tmp_path)
    create_approved(home, BUGFIX_FLOW)
    run_until(home, "be/code/implement")
    data = instructions(home, "be/code/implement")
    assert data["fragment"] == "be/code"
    assert data["fragmentName"] == "backend-code"
    assert data["fragmentDir"] == str(home.resolve() / "fragments" / "backend-code")


def test_gate_template_paths(tmp_path: Path) -> None:
    home = project(tmp_path)
    create_approved(home, BUGFIX_FLOW)
    run_until(home, "be/tests/check")
    data = instructions(home, "be/tests/check")
    assert data["fragmentName"] == "backend-tests"
    assert "templatePath" not in data
    for verdict in ("pass", "fail"):
        assert Path(data["templatePaths"][verdict]).read_text() == data["templates"][verdict]


def test_registry_fragment_paths_point_into_the_verified_snapshot(tmp_path: Path) -> None:
    _, home = registry_project(tmp_path)
    sync(home)
    create_approved(home, BUGFIX_FLOW)
    data = instructions(home, "requirements/proposal")
    folder = Path(data["fragmentDir"])
    assert folder.is_dir() and folder.name == "requirements"
    assert folder.is_relative_to(registry_store.store_root().resolve())
    assert not (home / "fragments").exists()
    assert Path(data["instructionPath"]).read_text() == data["instruction"]
    assert Path(data["instructionPath"]).is_relative_to(folder)


def test_text_report_shows_the_paths(tmp_path: Path) -> None:
    from typer.testing import CliRunner

    from loopspec.cli import app

    home = project(tmp_path)
    create_approved(home, BUGFIX_FLOW)
    result = CliRunner().invoke(
        app,
        ["node", "instructions", "-c", CHANGE, "-n", "requirements/proposal", "--home", str(home)],
    )
    folder = home.resolve() / "fragments" / "requirements"
    assert f"\nfragmentDir:         {folder}\n" in result.stdout
    assert "\nfragmentName:        requirements\n" in result.stdout
    assert "relative to fragmentDir" in result.stdout
