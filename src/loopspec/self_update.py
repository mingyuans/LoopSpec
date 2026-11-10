"""`loopspec update`: install a newer LoopSpec release over the running one.

The same steps install.sh takes, done from inside the CLI:

1. Pick the release. By default that is GitHub's "latest" release, which is
   always a stable one; `--version` pins a tag; `--beta` reads the releases
   Atom feed and takes the highest tag in it, beta included.
2. Fetch that release's checksums.txt -- the latest one from GitHub's constant
   `releases/latest/download/` URL, or the chosen tag's -- and read the
   version from its wheel line. When a tag was chosen, that version must be
   the one the tag maps to.
3. Download that version's wheel from its tag URL and verify it against exactly
   one checksums.txt line. There is deliberately no way to skip this.
4. Install the local, already-verified file with `uv tool install --force`, or
   `pipx install --force` when uv is missing.

Tags and package versions map one to one: the stable tag `vX.Y.Z` is the
package version `X.Y.Z`, and the beta tag `vX.Y.Z-beta` is the PEP 440 package
version `X.Y.Zb0` (see `release_tag` and `package_version`). Versions are
ordered by `version_key`, so the default and `--beta` never downgrade: an
installed 1.1.4b0 stays put while the latest stable release is 1.1.3 and moves
on once 1.2.0 is out. Only an explicit `--version` reinstalls or downgrades.

Every externally supplied version -- `--version`, a tag in the feed, the wheel
name in checksums.txt -- passes `validate_version` / `package_version` before
it reaches a URL, a filename or an argv; feed tags that do not map are
dropped. The feed is scanned with a fixed regular expression, never an XML
parser. Downloads are https-only (redirects included), time-limited and
size-capped; installers run without a shell.

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
    UpdateReleaseNotFoundError,
    UpdateVerifyFailedError,
)

__all__ = [
    "LATEST_CHECKSUMS_URL",
    "MAX_CHECKSUMS_BYTES",
    "MAX_FEED_BYTES",
    "MAX_WHEEL_BYTES",
    "RELEASES",
    "RELEASES_FEED_URL",
    "TIMEOUT_SECONDS",
    "UpdateFetchFailedError",
    "UpdateInstallFailedError",
    "UpdateInstallerMissingError",
    "UpdateInvalidVersionError",
    "UpdateReleaseNotFoundError",
    "UpdateResult",
    "UpdateVerifyFailedError",
    "default_runner",
    "expected_digest",
    "https_fetch",
    "is_beta",
    "package_version",
    "pick_installer",
    "release_tag",
    "run_update",
    "validate_version",
    "version_from_checksums",
    "version_key",
]

RELEASES = "https://github.com/mingyuans/LoopSpec/releases"
LATEST_CHECKSUMS_URL = f"{RELEASES}/latest/download/checksums.txt"
RELEASES_FEED_URL = f"{RELEASES}.atom"

#: install.sh's VERSION_PATTERN plus the bare `-beta` tag suffix; always
#: applied with fullmatch.
VERSION_PATTERN = re.compile(
    r"[0-9]+\.[0-9]+\.[0-9]+(?:[._-]?(?:a|b|rc|alpha|beta|dev|post)[0-9]+|-beta)?"
)
#: The only two release shapes: stable, and beta as a tag body or a package version.
STABLE_PATTERN = re.compile(r"[0-9]+\.[0-9]+\.[0-9]+")
BETA_TAG_PATTERN = re.compile(r"([0-9]+\.[0-9]+\.[0-9]+)-beta")
BETA_VERSION_PATTERN = re.compile(r"([0-9]+\.[0-9]+\.[0-9]+)b0")
#: `version_key`'s split of an already validated version into base and suffix.
_KEY_PATTERN = re.compile(r"([0-9]+)\.([0-9]+)\.([0-9]+)(.*)")
#: Release links in the Atom feed; every captured tag is still validated.
FEED_TAG_PATTERN = re.compile(
    r'href="https://github\.com/mingyuans/LoopSpec/releases/tag/(v[^"]+)"'
)
WHEEL_PATTERN = re.compile(r"loopspec-(.*)-py3-none-any\.whl")
SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")

MAX_CHECKSUMS_BYTES = 64 * 1024
MAX_FEED_BYTES = 512 * 1024
#: How many feed tags --beta tries, newest first, when a release is not published yet.
MAX_FEED_CANDIDATES = 3
MAX_WHEEL_BYTES = 50 * 1024 * 1024
TIMEOUT_SECONDS = 30
CHUNK_BYTES = 64 * 1024

#: (url, max_bytes) -> body
Fetcher = Callable[[str, int], bytes]
#: argv -> exit code
Runner = Callable[[list[str]], int]
#: shutil.which
Which = Callable[[str], "str | None"]
#: (X, Y, Z, rank) -- see `version_key`
VersionKey = tuple[int, int, int, int]

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


def package_version(tag_or_version: str) -> str:
    """The package version of a release: `v1.1.4-beta` / `1.1.4-beta` / `1.1.4b0` -> `1.1.4b0`.

    Accepts a tag (`vX.Y.Z`, `vX.Y.Z-beta`) or a version (`X.Y.Z`, `X.Y.Z-beta`,
    `X.Y.Zb0`); every other shape raises `UpdateInvalidVersionError`.
    """

    body = tag_or_version.removeprefix("v")
    is_tag = body != tag_or_version
    if STABLE_PATTERN.fullmatch(body):
        return body
    beta = BETA_TAG_PATTERN.fullmatch(body)
    if beta is None and not is_tag:
        beta = BETA_VERSION_PATTERN.fullmatch(body)
    if beta is None:
        raise UpdateInvalidVersionError(
            f"not a LoopSpec release (X.Y.Z or X.Y.Z-beta): {tag_or_version!r}",
            "Pass a release version such as 2.1.0 or 2.1.0-beta.",
        )
    return f"{beta.group(1)}b0"


def release_tag(version: str) -> str:
    """The git tag of a release: `1.1.4b0` / `1.1.4-beta` -> `v1.1.4-beta`, `1.2.0` -> `v1.2.0`."""

    normalized = package_version(version)
    beta = BETA_VERSION_PATTERN.fullmatch(normalized)
    return f"v{beta.group(1)}-beta" if beta else f"v{normalized}"


def is_beta(version: str) -> bool:
    """Whether a release tag or version is a beta (`X.Y.Z-beta` / `X.Y.Zb0`)."""

    return BETA_VERSION_PATTERN.fullmatch(package_version(version)) is not None


def version_key(version: str) -> VersionKey:
    """Sort key `(X, Y, Z, rank)`: rank 0 pre-release, 1 final, 2 post-release.

    So 1.1.3 < 1.1.4b0 < 1.1.4 < 1.1.4.post1 < 1.2.0. Pre-releases of one base
    tie with each other; LoopSpec itself only publishes X.Y.Z and X.Y.Zb0.
    """

    match = _KEY_PATTERN.fullmatch(validate_version(version))
    if match is None:  # unreachable: VERSION_PATTERN implies the X.Y.Z prefix
        raise UpdateInvalidVersionError(f"not a valid release version: {version!r}")
    suffix = match.group(4)
    rank = 1 if not suffix else 2 if "post" in suffix else 0
    return int(match.group(1)), int(match.group(2)), int(match.group(3)), rank


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
                    raise UpdateFetchFailedError(f"{url} is larger than the {max_bytes}-byte limit")
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            raise UpdateReleaseNotFoundError(f"could not download {url} (HTTP 404)") from None
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


def _feed_tags(fetch: Fetcher) -> list[str]:
    """Release tags in the Atom feed, beta included, newest first; malformed tags are dropped."""

    try:
        text = fetch(RELEASES_FEED_URL, MAX_FEED_BYTES).decode("utf-8")
    except UnicodeDecodeError:
        raise UpdateFetchFailedError(f"{RELEASES_FEED_URL} is not UTF-8 text") from None
    found: dict[str, VersionKey] = {}
    for raw in FEED_TAG_PATTERN.findall(text):
        try:
            normalized = package_version(raw)
        except UpdateInvalidVersionError:
            continue
        found.setdefault(release_tag(normalized), version_key(normalized))
    if not found:
        raise UpdateFetchFailedError(f"{RELEASES_FEED_URL} lists no LoopSpec release tag")
    return sorted(found, key=found.__getitem__, reverse=True)


def _fetch_checksums(fetch: Fetcher, url: str) -> str:
    try:
        return fetch(url, MAX_CHECKSUMS_BYTES).decode("utf-8")
    except UnicodeDecodeError:
        raise UpdateFetchFailedError(f"{url} is not UTF-8 text") from None


def _newest_published(fetch: Fetcher) -> tuple[str, str]:
    """The newest feed tag whose release serves a checksums.txt, and that file's text.

    A tag can be listed before its release exists (CI still running, or failed), so
    up to MAX_FEED_CANDIDATES tags are tried, newest first, before giving up. Only a
    definite HTTP 404 moves on to the next tag: a timeout, a 5xx, an oversized or
    undecodable checksums.txt is a real failure and stops the update, so a broken
    newest release is reported rather than silently skipped.
    """

    error: UpdateReleaseNotFoundError | None = None
    for tag in _feed_tags(fetch)[:MAX_FEED_CANDIDATES]:
        url = f"{RELEASES}/download/{tag}/checksums.txt"
        try:
            body = fetch(url, MAX_CHECKSUMS_BYTES)
        except UpdateReleaseNotFoundError as exc:
            error = exc
            continue
        try:
            return tag, body.decode("utf-8")
        except UnicodeDecodeError:
            raise UpdateFetchFailedError(f"{url} is not UTF-8 text") from None
    assert error is not None
    raise error


def _installed_key(current: str) -> VersionKey | None:
    """`version_key` of the running version; None (older than any release) if unparsable."""

    try:
        return version_key(current)
    except UpdateInvalidVersionError:
        return None


def _checksums_version(text: str, tag: str | None) -> str:
    """The wheel's version; for a chosen tag it must be exactly the tag's package version."""

    if tag is None:
        latest = version_from_checksums(text)
        if not STABLE_PATTERN.fullmatch(latest):
            # releases/latest must name a stable release; a beta marked Latest by
            # mistake is refused, as install.sh does, rather than installed.
            raise UpdateFetchFailedError(
                f"the latest release ships loopspec {latest}, which is not a stable release",
                "Run `loopspec update --beta` to install pre-releases on purpose.",
            )
        return latest
    expected = package_version(tag)
    try:
        latest = version_from_checksums(text)
    except UpdateFetchFailedError:
        raise UpdateVerifyFailedError(
            f"release {tag}'s checksums.txt lists no wheel; nothing was installed"
        ) from None
    if latest != expected:
        raise UpdateVerifyFailedError(
            f"release {tag} ships loopspec {latest}, expected {expected}; nothing was installed"
        )
    return latest


def run_update(
    current: str,
    *,
    version: str | None = None,
    check: bool = False,
    beta: bool = False,
    fetch: Fetcher = https_fetch,
    run: Runner = default_runner,
    which: Which = shutil.which,
    on_download: Callable[[str], None] | None = None,
) -> UpdateResult:
    """Resolve, verify and install a release; see the module docstring."""

    if beta and version is not None:
        raise UpdateInvalidVersionError(
            "--beta and --version cannot be combined",
            "Pass either --beta (newest release, beta included) or --version, not both.",
        )
    tag: str | None = None
    if version is not None:
        tag = release_tag(package_version(validate_version(version)))
        text = _fetch_checksums(fetch, f"{RELEASES}/download/{tag}/checksums.txt")
    elif beta:
        tag, text = _newest_published(fetch)
    else:
        text = _fetch_checksums(fetch, LATEST_CHECKSUMS_URL)
    latest = _checksums_version(text, tag)

    current_key = _installed_key(current)
    newer = current_key is None or version_key(latest) > current_key
    if check:
        available = newer or (version is not None and latest != current)
        status: Status = "available" if available else "up_to_date"
        return UpdateResult(status, current, latest, None)
    if version is None and not newer:
        # The default and --beta never downgrade, e.g. from 1.1.4b0 to 1.1.3.
        return UpdateResult("up_to_date", current, latest, None)

    wheel_name = f"loopspec-{latest}-py3-none-any.whl"
    digest = expected_digest(text, wheel_name)
    if on_download is not None:
        on_download(latest)
    wheel_url = f"{RELEASES}/download/{release_tag(latest)}/{wheel_name}"
    payload = fetch(wheel_url, MAX_WHEEL_BYTES)
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
