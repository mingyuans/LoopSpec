"""Tests for hatch_version.py, the build backend's version source.

Every case loads a *copy* of the module from a temporary directory. The module
resolves paths and runs git relative to its own file, so the copy's directory is
what it inspects -- which is how a fake sdist or a fake tagged repository can be
built without touching this checkout.
"""

from __future__ import annotations

import importlib.util
import os
import re
import shutil
import subprocess
import types
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
MODULE = REPO_ROOT / "hatch_version.py"


def load(root: Path) -> types.ModuleType:
    """Import hatch_version.py as if it lived in ``root``."""

    shutil.copy(MODULE, root / "hatch_version.py")
    # Distinct module name per case: same-named modules would collide in the
    # import system and hand back the first one's ROOT.
    name = f"hatch_version_{abs(hash(str(root)))}"
    spec = importlib.util.spec_from_file_location(name, root / "hatch_version.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def git_repo_at(root: Path, tag: str | None) -> None:
    """Make ``root`` a repository with one commit, optionally tagged."""

    run = ["git", "-C", str(root)]
    subprocess.run([*run, "init", "-q"], check=True)
    (root / "file.txt").write_text("content\n", encoding="utf-8")
    subprocess.run([*run, "add", "."], check=True, capture_output=True)
    subprocess.run(
        [*run, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "c"],
        check=True,
        capture_output=True,
    )
    if tag is not None:
        subprocess.run([*run, "tag", tag], check=True, capture_output=True)


def pkg_info_at(root: Path, version: str) -> None:
    (root / "PKG-INFO").write_text(
        f"Metadata-Version: 2.4\nName: loopspec\nVersion: {version}\n",
        encoding="utf-8",
    )


@pytest.fixture(autouse=True)
def hermetic_env(monkeypatch: pytest.MonkeyPatch):
    """Neither the surrounding shell nor the developer's git config may decide the
    outcome: an exported version would preempt every case, and a global
    ``tag.gpgSign`` turns ``git tag`` into a signing prompt.
    """

    monkeypatch.delenv("LOOPSPEC_BUILD_VERSION", raising=False)
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_SYSTEM", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")


requires_git = pytest.mark.skipif(
    shutil.which("git") is None, reason="the git source needs a git executable"
)


# --- the individual sources ------------------------------------------------


def test_environment_variable_is_used(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("LOOPSPEC_BUILD_VERSION", "1.2.3")
    assert load(tmp_path).resolve_version() == "1.2.3"


@pytest.mark.parametrize("version", ["1.0.0rc1", "0.9.0.post1", "2.0.0-dev1"])
def test_environment_variable_accepts_the_prerelease_shapes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, version: str
):
    """The same shapes install.sh accepts, so a pinned install can find them."""

    monkeypatch.setenv("LOOPSPEC_BUILD_VERSION", version)
    assert load(tmp_path).resolve_version() == version


@pytest.mark.parametrize("value", ["0.2", "1.0.0-my-branch", "v1.0.0", "not-a-version", ""])
def test_malformed_environment_variable_is_an_error_not_a_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, value: str
):
    """Falling through would publish under a name the caller did not ask for."""

    monkeypatch.setenv("LOOPSPEC_BUILD_VERSION", value)
    module = load(tmp_path)
    with pytest.raises(ValueError, match="LOOPSPEC_BUILD_VERSION"):
        module.resolve_version()


@requires_git
def test_exact_tag_is_used_when_the_environment_is_unset(tmp_path: Path):
    git_repo_at(tmp_path, "v3.4.5")
    assert load(tmp_path).resolve_version() == "3.4.5"


@requires_git
def test_a_beta_tag_builds_as_its_normalized_version(tmp_path: Path):
    """v1.1.4-beta builds as 1.1.4b0, the same version CI stamps on that tag."""

    git_repo_at(tmp_path, "v1.1.4-beta")
    assert load(tmp_path).resolve_version() == "1.1.4b0"


@requires_git
@pytest.mark.parametrize(
    ("tag", "expected"),
    [("v1.1.4-beta1", "1.1.4-beta1"), ("v1.1.4-beta-beta", None), ("v1.1.4-rc", None)],
)
def test_other_beta_like_tags_are_not_mapped(tmp_path: Path, tag: str, expected: str | None):
    """Only the exact ``-beta`` suffix maps to ``b0``; anything else is passed to
    VERSION_RE as-is (None: rejected, so the dev version)."""

    git_repo_at(tmp_path, tag)
    module = load(tmp_path)
    assert module.resolve_version() == (expected or module.DEV_VERSION)


@requires_git
def test_a_commit_without_a_tag_falls_through_to_the_dev_version(tmp_path: Path):
    git_repo_at(tmp_path, None)
    module = load(tmp_path)
    assert module.resolve_version() == module.DEV_VERSION


@requires_git
def test_a_tag_that_is_not_a_version_is_ignored(tmp_path: Path):
    git_repo_at(tmp_path, "vendor-snapshot")
    module = load(tmp_path)
    assert module.resolve_version() == module.DEV_VERSION


def test_pkg_info_is_used_when_there_is_no_environment_or_git(tmp_path: Path):
    """Building a wheel from a released sdist: no tag, no environment variable."""

    pkg_info_at(tmp_path, "1.0.0")
    assert load(tmp_path).resolve_version() == "1.0.0"


def test_nothing_available_yields_the_dev_version(tmp_path: Path):
    module = load(tmp_path)
    assert module.resolve_version() == module.DEV_VERSION
    assert module.DEV_VERSION == "0.0.0.dev0"


# --- precedence ------------------------------------------------------------


@requires_git
def test_environment_wins_over_git_and_pkg_info(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    git_repo_at(tmp_path, "v3.4.5")
    pkg_info_at(tmp_path, "1.0.0")
    monkeypatch.setenv("LOOPSPEC_BUILD_VERSION", "9.9.9")
    assert load(tmp_path).resolve_version() == "9.9.9"


@requires_git
def test_git_wins_over_pkg_info(tmp_path: Path):
    git_repo_at(tmp_path, "v3.4.5")
    pkg_info_at(tmp_path, "1.0.0")
    assert load(tmp_path).resolve_version() == "3.4.5"


# --- the contract with the rest of the release machinery -------------------


def install_sh_pattern(name: str) -> str:
    text = (REPO_ROOT / "install.sh").read_text(encoding="utf-8")
    match = re.search(rf"^{name}='(.*)'$", text, re.MULTILINE)
    assert match, f"install.sh no longer declares {name}"
    return match.group(1)


def install_sh_accepts(name: str, candidate: str) -> bool:
    # Exactly how install.sh applies it: no trailing newline, -q for the verdict.
    return (
        subprocess.run(
            ["grep", "-q", install_sh_pattern(name)],
            input=candidate,
            text=True,
            check=False,
        ).returncode
        == 0
    )


needs_grep = pytest.mark.skipif(
    shutil.which("grep") is None, reason="needs grep to run install.sh's gate"
)


@needs_grep
@pytest.mark.parametrize(
    "candidate",
    ["1.2.3", "1.2.0", "0.1.0", "0.2", "v1.0.0", "1.2.3.4", "not-a-version", ""],
)
def test_the_two_version_gates_agree_on_stable_shapes(tmp_path: Path, candidate: str):
    """One rule, two implementations: on stable-shaped input, drift would let a
    release be published under a version install.sh then refuses to download.

    install.sh installs stable releases only, so its STABLE_PATTERN is the gate
    compared here; hatch also accepts pre-release shapes, covered below.
    """

    ours = load(tmp_path).VERSION_RE.match(candidate) is not None
    theirs = install_sh_accepts("STABLE_PATTERN", candidate)
    assert ours == theirs, f"{candidate!r}: hatch_version={ours}, install.sh={theirs}"


@needs_grep
@pytest.mark.parametrize("candidate", ["1.1.4b0", "1.0.0rc1", "0.9.0.post1", "2.0.0-dev1"])
def test_install_sh_refuses_what_hatch_builds_as_a_pre_release(tmp_path: Path, candidate: str):
    """Hatch builds betas; install.sh must refuse to install them."""

    assert load(tmp_path).VERSION_RE.match(candidate)
    assert not install_sh_accepts("STABLE_PATTERN", candidate)


@needs_grep
@pytest.mark.parametrize("candidate", ["1.2.3", "1.1.4b0", "0.0.0.dev0", "v1.0.0", "0.2", ""])
def test_install_sh_can_parse_every_version_hatch_builds(tmp_path: Path, candidate: str):
    """VERSION_PATTERN is what install.sh parses out of checksums.txt."""

    ours = load(tmp_path).VERSION_RE.match(candidate) is not None
    assert ours == install_sh_accepts("VERSION_PATTERN", candidate), candidate


@pytest.mark.parametrize("value", ["1.2.0", "1.1.4-beta", "v1.2.0", "v1.1.4-beta"])
def test_tag_mapping_agrees_with_self_update(tmp_path: Path, value: str):
    """hatch_version cannot import loopspec, so it repeats the tag -> version
    mapping; this keeps the copy equal to the single source of truth."""

    from loopspec.self_update import package_version

    assert load(tmp_path).tag_version(value) == package_version(value)


def test_this_repository_declares_no_release_version(tmp_path: Path):
    """The point of the whole module: the tag decides, so nothing else may name a
    release. The only version literal left in the tree is the dev placeholder.
    """

    pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'dynamic = ["version"]' in pyproject
    assert not re.search(r"^version = ", pyproject, re.MULTILINE)

    dev_version = load(tmp_path).DEV_VERSION
    init = (REPO_ROOT / "src" / "loopspec" / "__init__.py").read_text(encoding="utf-8")
    assigned = re.findall(r'__version__ = "([^"]+)"', init)
    assert assigned == [dev_version], f"unexpected version literal in __init__.py: {assigned}"
