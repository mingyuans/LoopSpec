"""Tests for install.sh.

The integrity check is the one control in the installer that must never fail
open, so it is exercised against fixtures rather than reviewed by eye. The
script's shell functions are loaded by stripping the trailing `main "$@"` call,
which is the only line with a side effect.
"""

import re
import shutil
import subprocess
from pathlib import Path

import pytest

INSTALL_SH = Path(__file__).resolve().parent.parent / "install.sh"
WHEEL = "loopspec-0.1.0-py3-none-any.whl"
# sha256 of b"wheel bytes\n", so the fixtures have a checksum that can pass.
WHEEL_BODY = "wheel bytes\n"
WHEEL_SHA = "d0995fbab28019f357bfaa8021396aa90224dafc0b6bda07afeeb2a83097fdd6"


@pytest.fixture(scope="module")
def sourceable(tmp_path_factory) -> Path:
    """install.sh with its final `main "$@"` line removed, so it can be sourced."""
    lines = INSTALL_SH.read_text(encoding="utf-8").splitlines(keepends=True)
    kept = [line for line in lines if line.strip() != 'main "$@"']
    assert len(kept) == len(lines) - 1, "expected exactly one `main \"$@\"` call"
    path = tmp_path_factory.mktemp("lib") / "install_lib.sh"
    path.write_text("".join(kept), encoding="utf-8")
    return path


def call(sourceable: Path, workdir: Path, snippet: str) -> subprocess.CompletedProcess[str]:
    script = f'. "{sourceable}"\n{snippet}\n'
    return subprocess.run(
        ["sh", "-c", script],
        cwd=workdir,
        capture_output=True,
        text=True,
        check=False,
    )


def extract(sourceable: Path, workdir: Path, checksums: str) -> subprocess.CompletedProcess[str]:
    (workdir / "checksums.txt").write_text(checksums, encoding="utf-8")
    return call(
        sourceable,
        workdir,
        f'extract_checksum_line checksums.txt "{WHEEL}" wheel.sha256',
    )


def test_exact_entry_is_extracted(sourceable: Path, tmp_path: Path):
    result = extract(
        sourceable,
        tmp_path,
        f"{WHEEL_SHA}  {WHEEL}\ndeadbeef  loopspec-0.1.0.tar.gz\n",
    )
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "wheel.sha256").read_text().strip() == f"{WHEEL_SHA}  {WHEEL}"


def test_missing_entry_fails(sourceable: Path, tmp_path: Path):
    result = extract(sourceable, tmp_path, "deadbeef  loopspec-0.1.0.tar.gz\n")
    assert result.returncode != 0
    assert "no checksum entry" in result.stderr


def test_empty_checksums_file_fails(sourceable: Path, tmp_path: Path):
    result = extract(sourceable, tmp_path, "")
    assert result.returncode != 0
    assert "no checksum entry" in result.stderr


def test_html_error_page_fails(sourceable: Path, tmp_path: Path):
    result = extract(sourceable, tmp_path, "<html><body>404: Not Found</body></html>\n")
    assert result.returncode != 0
    assert "no checksum entry" in result.stderr


def test_duplicate_entries_fail(sourceable: Path, tmp_path: Path):
    result = extract(
        sourceable,
        tmp_path,
        f"{WHEEL_SHA}  {WHEEL}\ncafebabe  {WHEEL}\n",
    )
    assert result.returncode != 0
    assert "ambiguous" in result.stderr


def test_similar_version_is_not_matched(sourceable: Path, tmp_path: Path):
    """0.1.0 must not match 0.1.0.post1 -- the comparison is exact, not substring."""
    result = extract(
        sourceable,
        tmp_path,
        f"{WHEEL_SHA}  loopspec-0.1.0.post1-py3-none-any.whl\n",
    )
    assert result.returncode != 0
    assert "no checksum entry" in result.stderr


def test_binary_mode_marker_is_tolerated(sourceable: Path, tmp_path: Path):
    """`sha256sum -b` writes `*name`; the marker is not part of the filename."""
    result = extract(sourceable, tmp_path, f"{WHEEL_SHA} *{WHEEL}\n")
    assert result.returncode == 0, result.stderr


@pytest.mark.skipif(
    shutil.which("sha256sum") is None and shutil.which("shasum") is None,
    reason="needs sha256sum or shasum",
)
def test_verify_checksum_accepts_matching_wheel(sourceable: Path, tmp_path: Path):
    (tmp_path / WHEEL).write_text(WHEEL_BODY, encoding="utf-8")
    (tmp_path / "wheel.sha256").write_text(f"{WHEEL_SHA}  {WHEEL}\n", encoding="utf-8")
    result = call(sourceable, tmp_path, f'verify_checksum "{tmp_path}"')
    assert result.returncode == 0, result.stderr


@pytest.mark.skipif(
    shutil.which("sha256sum") is None and shutil.which("shasum") is None,
    reason="needs sha256sum or shasum",
)
def test_verify_checksum_rejects_tampered_wheel(sourceable: Path, tmp_path: Path):
    (tmp_path / WHEEL).write_text("tampered\n", encoding="utf-8")
    (tmp_path / "wheel.sha256").write_text(f"{WHEEL_SHA}  {WHEEL}\n", encoding="utf-8")
    result = call(sourceable, tmp_path, f'verify_checksum "{tmp_path}"')
    assert result.returncode != 0
    assert "checksum verification failed" in result.stderr


@pytest.mark.parametrize(
    "version",
    ["0.1.0", "1.2.3", "1.0.0rc1", "0.9.0.post1", "2.0.0b2"],
)
def test_valid_versions_accepted(sourceable: Path, tmp_path: Path, version: str):
    result = call(sourceable, tmp_path, f'validate_version "{version}"')
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(
    "version",
    [
        "0.1",
        "v0.1.0",
        "0.1.0-my-branch",
        "../../etc/passwd",
        "0.1.0; touch pwned",
        "0.1.0$(touch pwned)",
        "",
    ],
)
def test_invalid_versions_rejected(sourceable: Path, tmp_path: Path, version: str):
    result = call(sourceable, tmp_path, f"validate_version '{version}'")
    assert result.returncode != 0
    assert not (tmp_path / "pwned").exists()


def code_lines() -> list[str]:
    """Executable lines only -- the prose in comments mentions what is avoided."""
    return [
        line
        for line in INSTALL_SH.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


def test_script_has_no_privilege_escalation_or_eval():
    code = "\n".join(code_lines())
    for forbidden in ("sudo", "eval", "--ignore-missing"):
        assert forbidden not in code, f"install.sh must not use {forbidden}"


def test_script_offers_no_way_to_skip_verification():
    """LOOPSPEC_VERSION is the only environment variable the script reads."""
    pattern = r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::-[^}]*)?\}"
    env_reads = set(re.findall(pattern, "\n".join(code_lines())))
    assert env_reads == {"LOOPSPEC_VERSION"}, env_reads


def test_main_is_called_on_the_last_line():
    """A truncated `curl | sh` must not execute a partial install."""
    lines = [line for line in INSTALL_SH.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert lines[-1] == 'main "$@"'


# --- version resolution -------------------------------------------------
#
# The installer used to read the version from api.github.com, which allows 60
# unauthenticated requests per hour per IP -- shared by everyone behind a NAT,
# so the lookup failed with 403 for reasons unrelated to this repository. It now
# reads `releases/latest/download/checksums.txt`, a constant github.com URL with
# no such cap, and takes the version from the wheel filename inside it.
#
# curl is stubbed rather than called: these assert which URLs the script asks
# for, which is exactly what a real request would hide.

CURL_STUB = """#!/bin/sh
# Record the full argument list, then honour `-o <path>` the way curl would.
printf '%s\\n' "$*" >>"$STUB_LOG"
out=""
prev=""
for arg in "$@"; do
\t[ "$prev" = "-o" ] && out=$arg
\tprev=$arg
done
[ "$STUB_EXIT" -eq 0 ] || exit "$STUB_EXIT"
[ -z "$out" ] || printf '%s' "$STUB_BODY" >"$out"
exit 0
"""

LATEST_CHECKSUMS = (
    f"{WHEEL_SHA}  {WHEEL}\n" "deadbeef  loopspec-0.1.0.tar.gz\n"
)


def resolve(
    sourceable: Path,
    workdir: Path,
    *,
    body: str = LATEST_CHECKSUMS,
    exit_code: int = 0,
    env: dict[str, str] | None = None,
) -> tuple[subprocess.CompletedProcess[str], list[str]]:
    """Run `resolve_release` with a stubbed curl; return the result and the URLs asked for."""
    bindir = workdir / "bin"
    bindir.mkdir()
    stub = bindir / "curl"
    stub.write_text(CURL_STUB, encoding="utf-8")
    stub.chmod(0o755)

    log = workdir / "curl.log"
    full_env = {
        "PATH": f"{bindir}:/usr/bin:/bin",
        "STUB_LOG": str(log),
        "STUB_BODY": body,
        "STUB_EXIT": str(exit_code),
        **(env or {}),
    }
    result = subprocess.run(
        ["sh", "-c", f'. "{sourceable}"\nresolve_release "{workdir}"\n'],
        cwd=workdir,
        capture_output=True,
        text=True,
        check=False,
        env=full_env,
    )
    calls = log.read_text(encoding="utf-8").splitlines() if log.exists() else []
    return result, calls


def test_latest_version_comes_from_the_constant_checksums_url(sourceable: Path, tmp_path: Path):
    result, calls = resolve(sourceable, tmp_path)
    assert result.returncode == 0, result.stderr
    assert result.stdout == "0.1.0"
    assert len(calls) == 1
    assert "releases/latest/download/checksums.txt" in calls[0]


def test_version_resolution_never_touches_the_github_api(sourceable: Path, tmp_path: Path):
    """The 403 this replaced came from the API's 60-request hourly cap."""
    _, calls = resolve(sourceable, tmp_path)
    assert not any("api.github.com" in call for call in calls)
    assert "api.github.com" not in "\n".join(code_lines())


def test_pinned_version_reads_that_release_not_the_latest(sourceable: Path, tmp_path: Path):
    result, calls = resolve(sourceable, tmp_path, env={"LOOPSPEC_VERSION": "0.1.0"})
    assert result.returncode == 0, result.stderr
    assert result.stdout == "0.1.0"
    assert len(calls) == 1
    assert "releases/download/v0.1.0/checksums.txt" in calls[0]
    assert "latest" not in calls[0]


def test_pinned_version_is_validated_before_reaching_a_url(sourceable: Path, tmp_path: Path):
    result, calls = resolve(sourceable, tmp_path, env={"LOOPSPEC_VERSION": "0.1.0; rm -rf /"})
    assert result.returncode != 0
    assert "not a valid version" in result.stderr
    assert calls == [], "a rejected version must not produce a request"


def test_binary_mode_marker_does_not_hide_the_version(sourceable: Path, tmp_path: Path):
    result, _ = resolve(sourceable, tmp_path, body=f"{WHEEL_SHA} *{WHEEL}\n")
    assert result.returncode == 0, result.stderr
    assert result.stdout == "0.1.0"


def test_checksums_without_a_wheel_entry_fails(sourceable: Path, tmp_path: Path):
    result, _ = resolve(sourceable, tmp_path, body="deadbeef  loopspec-0.1.0.tar.gz\n")
    assert result.returncode != 0
    assert "no wheel entry" in result.stderr


def test_html_error_page_yields_no_version(sourceable: Path, tmp_path: Path):
    result, _ = resolve(sourceable, tmp_path, body="<html><body>Not Found</body></html>\n")
    assert result.returncode != 0
    assert "no wheel entry" in result.stderr


def test_malformed_version_in_checksums_is_rejected(sourceable: Path, tmp_path: Path):
    """A tampered filename must not become part of a download URL."""
    body = f"{WHEEL_SHA}  loopspec-1.0.3; rm -rf /-py3-none-any.whl\n"
    result, _ = resolve(sourceable, tmp_path, body=body)
    assert result.returncode != 0
    assert "not a valid version" in result.stderr


def test_unreachable_release_points_at_the_pin_escape_hatch(sourceable: Path, tmp_path: Path):
    result, _ = resolve(sourceable, tmp_path, exit_code=22)
    assert result.returncode != 0
    assert "LOOPSPEC_VERSION" in result.stderr


def test_wheel_is_downloaded_from_the_versioned_tag_url():
    """`latest/download` resolves the version; the wheel then comes from the
    immutable tag URL, so a release landing mid-run cannot swap the bytes."""
    code = "\n".join(code_lines())
    assert 'wheel_url="$RELEASES/download/v$version/$wheel_name"' in code
