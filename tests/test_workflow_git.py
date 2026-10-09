from pathlib import Path

import pytest

from loopspec.errors import WorkflowError
from loopspec.workflow_git import fixed_baseline, git


def init_repository(root: Path):
    git(root, ["init", "-q"])
    git(root, ["config", "user.name", "LoopSpec Test"])
    git(root, ["config", "user.email", "test@example.invalid"])
    (root / "initial.md").write_text("initial")
    git(root, ["add", "--", "initial.md"])
    git(root, ["commit", "-q", "-m", "initial"])


def test_fixed_baseline_does_not_follow_new_head(tmp_path: Path):
    init_repository(tmp_path)
    original, repository = fixed_baseline(tmp_path)
    (tmp_path / "initial.md").write_text("next")
    git(tmp_path, ["add", "--", "initial.md"])
    git(tmp_path, ["commit", "-q", "-m", "next"])
    assert fixed_baseline(tmp_path)[0] != original
    assert fixed_baseline(tmp_path, original) == (original, repository)


@pytest.mark.parametrize("baseline", ["HEAD~1", "--help", "x; echo unsafe"])
def test_baseline_is_not_an_option_or_expression(tmp_path: Path, baseline):
    with pytest.raises(WorkflowError):
        fixed_baseline(tmp_path, baseline)
