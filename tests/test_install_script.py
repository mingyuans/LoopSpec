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
