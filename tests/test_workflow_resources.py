from pathlib import Path

import pytest
from typer.testing import CliRunner

from loopspec.cli import app
from loopspec.errors import WorkflowError
from loopspec.workflow_resources import install_resources


def test_init_installs_new_resources_without_overwriting_customization(tmp_path: Path):
    home = tmp_path / "loopspec"
    runner = CliRunner()
    result = runner.invoke(app, ["init", str(home), "--tools", "none", "--json"])
    assert result.exit_code == 0, result.stdout
    selected = home / "fragments/security-review/fragment.yaml"
    selected.write_text("用户的路径映射")
    removed = home / "fragments/backend-tests"
    for path in removed.iterdir():
        path.unlink()
    removed.rmdir()
    copied = install_resources(home)
    assert selected.read_text() == "用户的路径映射"
    assert "fragments/backend-tests/fragment.yaml" in copied
    assert "fragments/backend-tests/check.instruction.md" in copied
    assert "fragments/backend-tests/check.pass.md" in copied
    assert "fragments/security-review/fragment.yaml" not in copied
    assert (home / "fragments/requirements/proposal.template.md").is_file()
    assert (home / "fragments/change-assurance/rules.yaml").is_file()
    assert (home / "profiles/frontend-small-change.yaml").is_file()


def test_install_rejects_link_in_destination(tmp_path: Path):
    home = tmp_path / "loopspec"
    home.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (home / "fragments").symlink_to(outside, target_is_directory=True)
    with pytest.raises(WorkflowError):
        install_resources(home)
    assert list(outside.iterdir()) == []
