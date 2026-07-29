"""Tests for .github/workflows/release.yml.

Two things are checked here:

* the invariants that can be read off the file (permissions, pinned actions, no
  credential persistence, no expression interpolation in shell bodies) -- these
  are the constraints the security review signed off on, and a later edit that
  breaks one of them should fail the build rather than be noticed by chance;
* the shell logic of the release steps, run against fixtures, since it decides
  what gets published.
"""

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

WORKFLOW = Path(__file__).resolve().parent.parent / ".github" / "workflows" / "release.yml"
VERSION_STEP = "Resolve and validate version from tag"
PUBLISH_STEP = "Publish release"
CHECKSUM_STEP = "Generate checksums"

PINNED_ACTIONS = {
    "actions/checkout": "3d3c42e5aac5ba805825da76410c181273ba90b1",
    "astral-sh/setup-uv": "c771a70e6277c0a99b617c7a806ffedaca235ff9",
}
# Steps that legitimately hold the token: everything else executes repository or
# third-party code and must not see it.
TOKEN_STEPS = {
    "Require the tagged commit to be on the default branch",
    "Require the release not to exist yet",
    PUBLISH_STEP,
}


@pytest.fixture(scope="module")
def workflow() -> dict:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def steps(workflow: dict, job: str) -> list[dict]:
    return workflow["jobs"][job]["steps"]


def step_named(workflow: dict, job: str, name: str) -> dict:
    for step in steps(workflow, job):
        if step.get("name") == name:
            return step
    raise AssertionError(f"no step named {name!r} in job {job!r}")


def run_snippet(body: str, cwd: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    # `-e` matches how Actions invokes a `run:` body (`bash -e {0}`), so a step
    # that would abort in CI also aborts here.
    return subprocess.run(
        ["bash", "-e", "-c", body],
        cwd=cwd,
        capture_output=True,
        text=True,
        env={"PATH": os.environ.get("PATH", "/usr/bin:/bin"), **env},
        check=False,
    )


# --- file-level invariants -------------------------------------------------


def test_default_permissions_are_read_only(workflow: dict):
    assert workflow["permissions"] == {"contents": "read"}


def test_only_the_release_job_can_write(workflow: dict):
    assert "permissions" not in workflow["jobs"]["verify"]
    assert workflow["jobs"]["release"]["permissions"] == {"contents": "write"}


def test_release_job_runs_only_on_tags(workflow: dict):
    assert workflow["jobs"]["release"]["if"] == "startsWith(github.ref, 'refs/tags/v')"
    assert workflow["jobs"]["release"]["needs"] == "verify"


def test_both_trigger_paths_are_declared(workflow: dict):
    # PyYAML parses the bare key `on` as the boolean True.
    push = workflow[True]["push"]
    assert push["branches"] == ["main"]
    assert push["tags"] == ["v[0-9]+.[0-9]+.[0-9]+*"]


def test_actions_are_pinned_to_commit_shas(workflow: dict):
    used = [
        step["uses"] for job in workflow["jobs"] for step in steps(workflow, job) if "uses" in step
    ]
    assert used, "expected at least one action"
    for ref in used:
        action, _, sha = ref.partition("@")
        assert re.fullmatch(r"[0-9a-f]{40}", sha), f"{ref} is not pinned to a commit sha"
        assert PINNED_ACTIONS[action] == sha


def test_checkout_never_persists_credentials(workflow: dict):
    checkouts = [
        step
        for job in workflow["jobs"]
        for step in steps(workflow, job)
        if step.get("uses", "").startswith("actions/checkout@")
    ]
    assert len(checkouts) == 2
    for step in checkouts:
        assert step["with"]["persist-credentials"] is False


def test_token_is_scoped_to_the_steps_that_call_gh(workflow: dict):
    assert "env" not in workflow, "the token must not be workflow-level"
    for job in workflow["jobs"]:
        assert "env" not in workflow["jobs"][job], f"the token must not be {job}-level"
    with_token = {
        step.get("name")
        for job in workflow["jobs"]
        for step in steps(workflow, job)
        if "env" in step and "GH_TOKEN" in step["env"]
    }
    assert with_token == TOKEN_STEPS


def test_build_step_has_no_token(workflow: dict):
    """`uv build` runs the build backend, which is third-party code."""
    for job in workflow["jobs"]:
        for step in steps(workflow, job):
            if "uv build" in (step.get("run") or "") or step.get("run") == "make build":
                assert "env" not in step or "GH_TOKEN" not in step["env"]


def test_no_expression_interpolation_inside_run_bodies(workflow: dict):
    """`${{ }}` expands before the shell runs, so an interpolated ref name would
    execute before any validation could reject it."""
    for job in workflow["jobs"]:
        for step in steps(workflow, job):
            body = step.get("run") or ""
            assert "${{" not in body, f"{job}/{step.get('name')} interpolates into its script"


def test_no_third_party_publish_or_artifact_actions(workflow: dict):
    used = [
        step["uses"] for job in workflow["jobs"] for step in steps(workflow, job) if "uses" in step
    ]
    actions = {ref.partition("@")[0] for ref in used}
    assert actions == set(PINNED_ACTIONS)


def test_publisher_and_installer_agree_on_asset_names(workflow: dict):
    """The filenames are the contract between the workflow and install.sh.

    They are built independently on each side, so drift here would only show up
    as a failed download after a release had already gone out.
    """
    install_sh = (WORKFLOW.parent.parent.parent / "install.sh").read_text(encoding="utf-8")
    publish = step_named(workflow, "release", PUBLISH_STEP)["run"]
    # Same template, different variable names for the version on each side.
    assert 'wheel_name="loopspec-$version-py3-none-any.whl"' in install_sh
    assert 'wheel="dist/loopspec-$VERSION-py3-none-any.whl"' in publish
    assert 'sdist="dist/loopspec-$VERSION.tar.gz"' in publish
    assert "checksums.txt" in install_sh and "checksums.txt" in publish


def test_built_artifacts_match_the_contract():
    """What hatchling actually produces, not what we assume it produces."""
    repo = WORKFLOW.parent.parent.parent
    version = (repo / "src" / "loopspec" / "__init__.py").read_text(encoding="utf-8")
    version = re.search(r'__version__ = "([^"]+)"', version).group(1)
    dist = repo / "dist"
    if not dist.is_dir():
        pytest.skip("no dist/ -- run `make build` first")
    names = {path.name for path in dist.iterdir()}
    assert f"loopspec-{version}-py3-none-any.whl" in names
    assert f"loopspec-{version}.tar.gz" in names


def test_assets_are_not_globbed(workflow: dict):
    body = step_named(workflow, "release", PUBLISH_STEP)["run"]
    assert "dist/*" not in body
    assert 'gh release create "$TAG"' in body
    assert "--target" not in body, "the tag already exists; it must not be created"


# --- the release steps' shell logic ---------------------------------------


def version_snippet(workflow: dict) -> str:
    return step_named(workflow, "release", VERSION_STEP)["run"]


@pytest.mark.parametrize("tag", ["v0.1.0", "v1.2.3", "v1.0.0rc1", "v0.9.0.post1"])
def test_valid_tags_resolve_to_a_version(workflow: dict, tmp_path: Path, tag: str):
    env_file = tmp_path / "github_env"
    env_file.touch()
    result = run_snippet(
        version_snippet(workflow),
        tmp_path,
        {"GITHUB_REF_NAME": tag, "GITHUB_ENV": str(env_file)},
    )
    assert result.returncode == 0, result.stderr
    written = dict(
        line.split("=", 1) for line in env_file.read_text().splitlines() if "=" in line
    )
    assert written == {"TAG": tag, "VERSION": tag[1:]}


@pytest.mark.parametrize(
    "tag",
    [
        "v0.2",
        "v0.2.0-my-branch",
        "vendor-snapshot",
        "v1.0.0$(touch pwned)",
        "v1.0.0; touch pwned",
        "v../../etc/passwd",
    ],
)
def test_invalid_tags_are_rejected_without_executing_anything(
    workflow: dict, tmp_path: Path, tag: str
):
    env_file = tmp_path / "github_env"
    env_file.touch()
    result = run_snippet(
        version_snippet(workflow),
        tmp_path,
        {"GITHUB_REF_NAME": tag, "GITHUB_ENV": str(env_file)},
    )
    assert result.returncode != 0
    assert "does not name a valid version" in result.stdout + result.stderr
    assert env_file.read_text() == "", "a rejected tag must not reach later steps"
    assert not (tmp_path / "pwned").exists(), "the tag name was executed"


@pytest.mark.skipif(
    shutil.which("sha256sum") is None,
    reason="the step calls sha256sum, which the CI runner has but macOS does not",
)
def test_checksums_use_bare_filenames(workflow: dict, tmp_path: Path):
    """install.sh matches entries by basename, so a `dist/` prefix would break it."""
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "loopspec-0.1.0-py3-none-any.whl").write_text("wheel\n")
    (dist / "loopspec-0.1.0.tar.gz").write_text("sdist\n")
    result = run_snippet(
        step_named(workflow, "release", CHECKSUM_STEP)["run"],
        tmp_path,
        {"VERSION": "0.1.0"},
    )
    assert result.returncode == 0, result.stderr
    names = [line.split()[1] for line in (tmp_path / "checksums.txt").read_text().splitlines()]
    assert names == ["loopspec-0.1.0-py3-none-any.whl", "loopspec-0.1.0.tar.gz"]


def publish_assets_snippet(workflow: dict) -> str:
    """The publish step's asset checks, with the `gh` call replaced by an echo."""
    body = step_named(workflow, "release", PUBLISH_STEP)["run"]
    head, sep, _ = body.partition("gh release create")
    assert sep, "expected a `gh release create` call"
    return head + 'printf "%s\\n" "$wheel" "$sdist" checksums.txt >published.txt\n'


def test_publish_accepts_exactly_the_contracted_assets(workflow: dict, tmp_path: Path):
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "loopspec-0.1.0-py3-none-any.whl").touch()
    (dist / "loopspec-0.1.0.tar.gz").touch()
    (tmp_path / "checksums.txt").touch()
    (dist / "unexpected-extra-file.txt").touch()

    result = run_snippet(publish_assets_snippet(workflow), tmp_path, {"VERSION": "0.1.0"})
    assert result.returncode == 0, result.stderr
    published = (tmp_path / "published.txt").read_text().split()
    assert published == [
        "dist/loopspec-0.1.0-py3-none-any.whl",
        "dist/loopspec-0.1.0.tar.gz",
        "checksums.txt",
    ]
    assert not any("unexpected-extra-file" in p for p in published)


@pytest.mark.parametrize("missing", ["loopspec-0.1.0-py3-none-any.whl", "loopspec-0.1.0.tar.gz"])
def test_publish_fails_when_an_asset_is_missing(workflow: dict, tmp_path: Path, missing: str):
    """Also catches a build whose output does not match the tag's version."""
    dist = tmp_path / "dist"
    dist.mkdir()
    for name in ("loopspec-0.1.0-py3-none-any.whl", "loopspec-0.1.0.tar.gz"):
        if name != missing:
            (dist / name).touch()
    (tmp_path / "checksums.txt").touch()

    result = run_snippet(publish_assets_snippet(workflow), tmp_path, {"VERSION": "0.1.0"})
    assert result.returncode != 0
    assert "missing release asset" in result.stdout + result.stderr
    assert not (tmp_path / "published.txt").exists()
