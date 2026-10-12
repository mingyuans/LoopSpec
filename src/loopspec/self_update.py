"""`loopspec update`: install a newer LoopSpec release over the running one.

The same steps install.sh takes, done from inside the CLI:

1. Fetch the release's checksums.txt -- the latest one from GitHub's constant
   `releases/latest/download/` URL, or a pinned tag's -- and read the version
   from its wheel line.
2. Download that version's wheel from its tag URL and verify it against exactly
   one checksums.txt line. There is deliberately no way to skip this.
3. Install the local, already-verified file with `uv tool install --force`, or
   `pipx install --force` when uv is missing.

Every externally supplied version passes `validate_version` before it reaches a
URL, a filename or an argv; downloads are https-only (redirects included),
time-limited and size-capped; installers run without a shell.

As with install.sh, checksums.txt and the wheel come from the same release: the
check catches corrupted or swapped downloads, not a compromised release.
"""

from __future__ import annotations

import hashlib
import hmac
import http.client
import re
import shutil
import subprocess
import tempfile
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import IO, Any, Literal
from urllib.parse import urlsplit

from .errors import (
    UpdateFetchFailedError,
    UpdateInstallerMissingError,
    UpdateInstallFailedError,
    UpdateInvalidVersionError,
    UpdateVerifyFailedError,
)

__all__ = [
    "LATEST_CHECKSUMS_URL",
    "MAX_CHECKSUMS_BYTES",
    "MAX_WHEEL_BYTES",
    "RELEASES",
    "TIMEOUT_SECONDS",
    "UpdateFetchFailedError",
    "UpdateInstallFailedError",
    "UpdateInstallerMissingError",
    "UpdateInvalidVersionError",
    "UpdateResult",
    "UpdateVerifyFailedError",
    "default_runner",
    "expected_digest",
    "https_fetch",
    "pick_installer",
    "run_update",
    "validate_version",
    "version_from_checksums",
]

RELEASES = "https://github.com/mingyuans/LoopSpec/releases"
LATEST_CHECKSUMS_URL = f"{RELEASES}/latest/download/checksums.txt"

#: install.sh's VERSION_PATTERN, always applied with fullmatch.
VERSION_PATTERN = re.compile(
    r"[0-9]+\.[0-9]+\.[0-9]+(?:[._-]?(?:a|b|rc|alpha|beta|dev|post)[0-9]+)?"
)
WHEEL_PATTERN = re.compile(r"loopspec-(.*)-py3-none-any\.whl")
SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")

MAX_CHECKSUMS_BYTES = 64 * 1024
MAX_WHEEL_BYTES = 50 * 1024 * 1024
TIMEOUT_SECONDS = 30
CHUNK_BYTES = 64 * 1024

#: (url, max_bytes) -> body
Fetcher = Callable[[str, int], bytes]
#: argv -> exit code
Runner = Callable[[list[str]], int]
#: shutil.which
Which = Callable[[str], "str | None"]

Status = Literal["up_to_date", "available", "updated"]


@dataclass(frozen=True)
class UpdateResult:
    status: Status
    current: str
    latest: str
    #: Which installer ran; None when nothing was installed.
    installer: str | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def validate_version(value: str) -> str:
    """The gate every external version string passes before it is used anywhere."""

    if not VERSION_PATTERN.fullmatch(value):
        raise UpdateInvalidVersionError(f"not a valid release version: {value!r}")
    return value


def _checksum_entries(text: str) -> list[tuple[str, str]]:
    """`<sha256>  [*]<name>` lines as (digest, name); anything else is skipped."""

    entries = []
    for line in text.splitlines():
        parts = line.split()
        if len(parts) == 2:
            entries.append((parts[0], parts[1].removeprefix("*")))
    return entries


def version_from_checksums(text: str) -> str:
    """The version named by checksums.txt's wheel line."""

    for _, name in _checksum_entries(text):
        match = WHEEL_PATTERN.fullmatch(name)
        if match:
            return validate_version(match.group(1))
    raise UpdateFetchFailedError("the release's checksums.txt lists no wheel")


def expected_digest(text: str, wheel_name: str) -> str:
    """The SHA256 for exactly `wheel_name`; zero or several lines are both failures."""

    digests = [digest for digest, name in _checksum_entries(text) if name == wheel_name]
    if len(digests) != 1:
        raise UpdateVerifyFailedError(
            f"expected one checksum entry for {wheel_name}, found {len(digests)}"
        )
    digest = digests[0].lower()
    if not SHA256_PATTERN.fullmatch(digest):
        raise UpdateVerifyFailedError(f"the checksum entry for {wheel_name} is not a SHA256")
    return digest


class _HttpsOnlyRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Follow redirects, but never off https (e.g. a downgrade to http)."""

    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: IO[bytes] | None,
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> urllib.request.Request | None:
        if urlsplit(newurl).scheme != "https":
            raise urllib.error.URLError("refusing a redirect that leaves https")
        return super().redirect_request(req, fp, code, msg, headers, newurl)  # type: ignore[arg-type]


def _build_opener() -> urllib.request.OpenerDirector:
    return urllib.request.build_opener(_HttpsOnlyRedirectHandler)


def https_fetch(url: str, max_bytes: int) -> bytes:
    """GET an https URL, with a timeout, refusing bodies larger than `max_bytes`."""

    if urlsplit(url).scheme != "https":
        raise UpdateFetchFailedError(f"refusing a non-https URL: {url}")
    body = bytearray()
    try:
        with _build_opener().open(url, timeout=TIMEOUT_SECONDS) as response:
            while chunk := response.read(CHUNK_BYTES):
                body += chunk
                if len(body) > max_bytes:
                    raise UpdateFetchFailedError(
                        f"{url} is larger than the {max_bytes}-byte limit"
                    )
    except urllib.error.HTTPError as exc:
        raise UpdateFetchFailedError(f"could not download {url} (HTTP {exc.code})") from None
    except (urllib.error.URLError, http.client.HTTPException, OSError, ValueError):
        raise UpdateFetchFailedError(f"could not download {url}") from None
    return bytes(body)


def pick_installer(wheel: str, which: Which = shutil.which) -> tuple[str, list[str]]:
    """uv first, pipx second -- install.sh's order."""

    if which("uv"):
        return "uv", ["uv", "tool", "install", "--force", wheel]
    if which("pipx"):
        return "pipx", ["pipx", "install", "--force", wheel]
    raise UpdateInstallerMissingError("need uv or pipx to install, found neither")


def default_runner(argv: list[str], *, stdout: IO[str] | None = None) -> int:
    """Run an installer without a shell; its output goes to `stdout` (default: inherited)."""

    return subprocess.run(argv, check=False, stdout=stdout).returncode


def run_update(
    current: str,
    *,
    version: str | None = None,
    check: bool = False,
    fetch: Fetcher = https_fetch,
    run: Runner = default_runner,
    which: Which = shutil.which,
    on_download: Callable[[str], None] | None = None,
) -> UpdateResult:
    """Resolve, verify and install a release; see the module docstring."""

    if version is None:
        checksums_url = LATEST_CHECKSUMS_URL
    else:
        checksums_url = f"{RELEASES}/download/v{validate_version(version)}/checksums.txt"

    try:
        text = fetch(checksums_url, MAX_CHECKSUMS_BYTES).decode("utf-8")
    except UnicodeDecodeError:
        raise UpdateFetchFailedError(f"{checksums_url} is not UTF-8 text") from None
    latest = version_from_checksums(text) if version is None else version

    if check or (version is None and latest == current):
        status: Status = "up_to_date" if latest == current else "available"
        return UpdateResult(status, current, latest, None)

    wheel_name = f"loopspec-{latest}-py3-none-any.whl"
    digest = expected_digest(text, wheel_name)
    if on_download is not None:
        on_download(latest)
    payload = fetch(f"{RELEASES}/download/v{latest}/{wheel_name}", MAX_WHEEL_BYTES)
    if not hmac.compare_digest(hashlib.sha256(payload).hexdigest(), digest):
        raise UpdateVerifyFailedError(
            f"{wheel_name} does not match the release's checksums.txt; nothing was installed"
        )

    installer: str | None = None
    try:
        with tempfile.TemporaryDirectory(prefix="loopspec-update-") as workdir:
            wheel_path = Path(workdir) / wheel_name
            wheel_path.write_bytes(payload)
            installer, argv = pick_installer(str(wheel_path), which)
            returncode = run(argv)
    except OSError as exc:
        # `installer` is still None when staging the wheel failed (disk full,
        # unwritable TMPDIR); otherwise the installer itself could not start.
        if installer is None:
            message = f"could not stage the wheel: {exc.strerror or exc}"
            raise UpdateInstallFailedError(message) from None
        if isinstance(exc, FileNotFoundError):
            message = f"{installer} was found on PATH but could not be run"
            raise UpdateInstallerMissingError(message) from None
        message = f"could not run {installer}: {exc.strerror or exc}"
        raise UpdateInstallFailedError(message) from None
    if returncode != 0:
        raise UpdateInstallFailedError(f"{installer} exited with status {returncode}")
    return UpdateResult("updated", current, latest, installer)
