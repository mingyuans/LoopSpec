"""Tests for scripts/check_version.py.

The script is not part of the installed package (it runs in CI before
dependencies exist), so it is exercised as a subprocess against fixture repos
rather than imported.
"""

import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "check_version.py"


def make_repo(root: Path, pyproject_version: str, init_body: str) -> Path:
    (root / "pyproject.toml").write_text(
        f'[project]\nname = "loopspec"\nversion = "{pyproject_version}"\n',
        encoding="utf-8",
    )
    init_py = root / "src" / "loopspec" / "__init__.py"
    init_py.parent.mkdir(parents=True)
    init_py.write_text(init_body, encoding="utf-8")
    return root


def run(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--repo-root", str(root), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def test_versions_agree_prints_version(tmp_path: Path):
    make_repo(tmp_path, "0.4.2", '__version__ = "0.4.2"\n')
    result = run(tmp_path)
    assert result.returncode == 0
    assert result.stdout.strip() == "0.4.2"


def test_version_drift_reports_both_values(tmp_path: Path):
    make_repo(tmp_path, "0.5.0", '__version__ = "0.4.2"\n')
    result = run(tmp_path)
    assert result.returncode != 0
    assert "0.5.0" in result.stderr
    assert "0.4.2" in result.stderr


def test_malformed_version_is_rejected(tmp_path: Path):
    make_repo(tmp_path, "0.4.2-my-branch", '__version__ = "0.4.2-my-branch"\n')
    result = run(tmp_path)
    assert result.returncode != 0
    assert "malformed" in result.stderr


def test_expect_matching_tag_version(tmp_path: Path):
    make_repo(tmp_path, "0.4.2", '__version__ = "0.4.2"\n')
    result = run(tmp_path, "--expect", "0.4.2")
    assert result.returncode == 0
    assert result.stdout.strip() == "0.4.2"


def test_expect_mismatching_tag_version_names_all_three(tmp_path: Path):
    make_repo(tmp_path, "0.4.2", '__version__ = "0.4.2"\n')
    result = run(tmp_path, "--expect", "0.5.0")
    assert result.returncode != 0
    assert "0.5.0" in result.stderr
    assert "pyproject.toml" in result.stderr
    assert "src/loopspec/__init__.py" in result.stderr


def test_malformed_expected_version_is_rejected(tmp_path: Path):
    """A tag name that slipped through the ref-filter glob must not be accepted."""
    make_repo(tmp_path, "0.4.2", '__version__ = "0.4.2"\n')
    result = run(tmp_path, "--expect", "0.4.2; rm -rf /")
    assert result.returncode != 0
    assert "malformed expected version" in result.stderr


def test_prerelease_versions_are_accepted(tmp_path: Path):
    make_repo(tmp_path, "1.0.0rc1", '__version__ = "1.0.0rc1"\n')
    result = run(tmp_path, "--expect", "1.0.0rc1")
    assert result.returncode == 0


def test_reads_dunder_version_without_importing_the_package(tmp_path: Path):
    """The module is parsed, not imported -- so unimportable code is irrelevant.

    CI runs this check before `uv sync`, so importing the package would fail on
    its own dependencies.
    """
    make_repo(
        tmp_path,
        "0.4.2",
        'import a_module_that_does_not_exist\n\n__version__ = "0.4.2"\n',
    )
    result = run(tmp_path)
    assert result.returncode == 0
    assert result.stdout.strip() == "0.4.2"


def test_missing_dunder_version_is_an_error(tmp_path: Path):
    make_repo(tmp_path, "0.4.2", "VERSION = 1\n")
    result = run(tmp_path)
    assert result.returncode != 0
    assert "__version__" in result.stderr


def test_missing_project_version_is_an_error(tmp_path: Path):
    root = tmp_path
    (root / "pyproject.toml").write_text('[project]\nname = "loopspec"\n', encoding="utf-8")
    init_py = root / "src" / "loopspec" / "__init__.py"
    init_py.parent.mkdir(parents=True)
    init_py.write_text('__version__ = "0.4.2"\n', encoding="utf-8")
    result = run(root)
    assert result.returncode != 0
    assert "project.version" in result.stderr


def test_real_repo_versions_agree():
    """Guards the actual repository, not a fixture."""
    result = subprocess.run(
        [sys.executable, str(SCRIPT)], capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr
