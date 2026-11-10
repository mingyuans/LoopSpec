"""`loopspec update`: resolve, verify and install a release without touching the network.

Every test injects the fetcher, the process runner and `which`, so nothing here
downloads a byte or runs an installer.
"""

from __future__ import annotations

import hashlib
import io
import json
import re
import urllib.error
import urllib.request
from pathlib import Path

import pytest
from typer.testing import CliRunner

from loopspec import self_update
from loopspec.cli import app
from loopspec.errors import LoopspecError
from loopspec.self_update import (
    LATEST_CHECKSUMS_URL,
    MAX_CHECKSUMS_BYTES,
    MAX_FEED_BYTES,
    MAX_WHEEL_BYTES,
    RELEASES,
    RELEASES_FEED_URL,
    UpdateResult,
    expected_digest,
    https_fetch,
    is_beta,
    package_version,
    pick_installer,
    release_tag,
    run_update,
    validate_version,
    version_from_checksums,
    version_key,
)

WHEEL_BYTES = b"pretend this is a wheel"


def wheel_name(version: str) -> str:
    return f"loopspec-{version}-py3-none-any.whl"


def checksums(version: str, payload: bytes = WHEEL_BYTES, *, star: bool = False) -> bytes:
    digest = hashlib.sha256(payload).hexdigest()
    marker = "*" if star else ""
    lines = [
        f"{hashlib.sha256(b'sdist').hexdigest()}  loopspec-{version}.tar.gz",
        f"{digest}  {marker}{wheel_name(version)}",
    ]
    return ("\n".join(lines) + "\n").encode()


class FakeNet:
    """Serves canned bodies by URL and records every request."""

    def __init__(self, routes: dict[str, bytes]) -> None:
        self.routes = routes
        self.calls: list[tuple[str, int]] = []

    def __call__(self, url: str, max_bytes: int) -> bytes:
        self.calls.append((url, max_bytes))
        if url not in self.routes:
            raise AssertionError(f"unexpected request: {url}")
        return self.routes[url]


class FakeRunner:
    def __init__(self, returncode: int = 0) -> None:
        self.returncode = returncode
        self.calls: list[list[str]] = []
        self.payloads: list[bytes] = []

    def __call__(self, argv: list[str]) -> int:
        self.calls.append(list(argv))
        self.payloads.append(Path(argv[-1]).read_bytes())
        return self.returncode


def which_of(*available: str):
    return lambda name: f"/usr/bin/{name}" if name in available else None


def tag_url(version: str, asset: str) -> str:
    return f"{RELEASES}/download/v{version}/{asset}"


def latest_routes(version: str, payload: bytes = WHEEL_BYTES) -> dict[str, bytes]:
    return {
        LATEST_CHECKSUMS_URL: checksums(version, payload),
        tag_url(version, wheel_name(version)): payload,
    }


def error_code(excinfo: pytest.ExceptionInfo[LoopspecError]) -> str:
    return excinfo.value.code


def release_url(tag: str, asset: str) -> str:
    return f"{RELEASES}/download/{tag}/{asset}"


def feed(*tags: str) -> bytes:
    """A trimmed releases.atom with one entry per tag, newest first."""

    entries = "".join(
        f"<entry><id>tag:github.com,2008:Repository/1/{tag}</id>"
        f'<link rel="alternate" type="text/html" '
        f'href="https://github.com/mingyuans/LoopSpec/releases/tag/{tag}"/>'
        f"<title>{tag}</title></entry>\n"
        for tag in tags
    )
    return f'<?xml version="1.0" encoding="UTF-8"?>\n<feed>\n{entries}</feed>\n'.encode()


def tagged_routes(tag: str, version: str, payload: bytes = WHEEL_BYTES) -> dict[str, bytes]:
    return {
        release_url(tag, "checksums.txt"): checksums(version, payload),
        release_url(tag, wheel_name(version)): payload,
    }


# --------------------------------------------------------------------------- #
# Parsing and validation


@pytest.mark.parametrize(
    "value",
    ["2.0.0", "10.20.30", "2.1.0rc1", "2.0.0.post1", "1.0.0-dev3", "1.1.4-beta", "1.1.4b0"],
)
def test_validate_version_accepts_release_versions(value: str) -> None:
    assert validate_version(value) == value


@pytest.mark.parametrize(
    "value",
    [
        "",
        "2.0",
        "v2.0.0",
        "v1.1.4-beta",
        "1.0;rm -rf /",
        "../1.0.0",
        "1.0.0\n",
        "1.0.0 ",
        "2.0.0x1",
        "1.1.4-my-branch",
        "1.1.4-beta\n",
        "1.1.4-betax",
    ],
)
def test_validate_version_rejects_anything_else(value: str) -> None:
    with pytest.raises(LoopspecError) as excinfo:
        validate_version(value)
    assert error_code(excinfo) == "update_invalid_version"


@pytest.mark.parametrize(
    ("given", "version", "tag", "beta"),
    [
        ("1.2.0", "1.2.0", "v1.2.0", False),
        ("v1.2.0", "1.2.0", "v1.2.0", False),
        ("1.1.4-beta", "1.1.4b0", "v1.1.4-beta", True),
        ("v1.1.4-beta", "1.1.4b0", "v1.1.4-beta", True),
        ("1.1.4b0", "1.1.4b0", "v1.1.4-beta", True),
        ("10.20.30-beta", "10.20.30b0", "v10.20.30-beta", True),
    ],
)
def test_tag_and_package_version_map_one_to_one(
    given: str, version: str, tag: str, beta: bool
) -> None:
    assert package_version(given) == version
    assert release_tag(given) == tag
    assert is_beta(given) is beta
    # The mapping round-trips both ways.
    assert package_version(release_tag(version)) == version
    assert release_tag(package_version(tag)) == tag


@pytest.mark.parametrize(
    "value",
    [
        "1.1.4-beta1",
        "1.1.4b1",
        "v1.1.4b0",
        "1.1.4rc1",
        "1.1.4-rc",
        "1.1.4-my-branch",
        "1.1.4.post1",
        "vv1.2.0",
        "1.2",
        "",
        '1.1.4-evil"',
    ],
)
def test_package_version_rejects_other_shapes(value: str) -> None:
    for function in (package_version, release_tag, is_beta):
        with pytest.raises(LoopspecError) as excinfo:
            function(value)
        assert error_code(excinfo) == "update_invalid_version"


def test_version_key_orders_betas_between_stable_releases() -> None:
    ordered = ["1.0.0", "1.1.3", "1.1.4b0", "1.1.4", "1.1.5b0", "1.2.0", "1.10.0", "2.0.0b0"]
    assert sorted(reversed(ordered), key=version_key) == ordered
    assert version_key("1.1.4b0") == (1, 1, 4, 0)
    assert version_key("1.1.4") == (1, 1, 4, 1)


@pytest.mark.parametrize("pre", ["1.1.4a1", "1.1.4rc1", "1.1.4.dev3", "1.1.4-beta2"])
def test_version_key_puts_other_prereleases_before_the_final(pre: str) -> None:
    assert version_key("1.1.3") < version_key(pre) < version_key("1.1.4")


def test_version_key_puts_post_releases_after_the_final() -> None:
    assert version_key("1.1.4") < version_key("1.1.4.post1") < version_key("1.1.5b0")


def test_version_key_validates_its_input() -> None:
    with pytest.raises(LoopspecError) as excinfo:
        version_key("1.1;id")
    assert error_code(excinfo) == "update_invalid_version"


def test_version_from_checksums_reads_a_beta_wheel() -> None:
    assert version_from_checksums(checksums("1.1.4b0").decode()) == "1.1.4b0"


def test_version_from_checksums_reads_the_wheel_line() -> None:
    assert version_from_checksums(checksums("2.1.0").decode()) == "2.1.0"
    assert version_from_checksums(checksums("2.1.0", star=True).decode()) == "2.1.0"


def test_version_from_checksums_without_a_wheel_line() -> None:
    with pytest.raises(LoopspecError) as excinfo:
        version_from_checksums(f"{'a' * 64}  loopspec-2.1.0.tar.gz\n")
    assert error_code(excinfo) == "update_fetch_failed"


def test_version_from_checksums_rejects_a_hostile_version() -> None:
    text = f"{'a' * 64}  loopspec-1.0;rm$IFS-rf$IFS~-py3-none-any.whl\n"
    with pytest.raises(LoopspecError) as excinfo:
        version_from_checksums(text)
    assert error_code(excinfo) == "update_invalid_version"


def test_expected_digest_needs_exactly_one_exact_line() -> None:
    name = wheel_name("2.1.0")
    text = checksums("2.1.0").decode()
    assert expected_digest(text, name) == hashlib.sha256(WHEEL_BYTES).hexdigest()

    # A longer name sharing the prefix must not match.
    near_miss = f"{'b' * 64}  loopspec-2.1.0.post1-py3-none-any.whl\n"
    for broken in ("", near_miss, text + text, f"{'z' * 64}  {name}\n", f"abc  {name}\n"):
        with pytest.raises(LoopspecError) as excinfo:
            expected_digest(broken, name)
        assert error_code(excinfo) == "update_verify_failed"


def test_pick_installer_prefers_uv_then_pipx() -> None:
    assert pick_installer("/tmp/x.whl", which_of("uv", "pipx")) == (
        "uv",
        ["uv", "tool", "install", "--force", "/tmp/x.whl"],
    )
    assert pick_installer("/tmp/x.whl", which_of("pipx")) == (
        "pipx",
        ["pipx", "install", "--force", "/tmp/x.whl"],
    )
    with pytest.raises(LoopspecError) as excinfo:
        pick_installer("/tmp/x.whl", which_of())
    assert error_code(excinfo) == "update_installer_missing"


# --------------------------------------------------------------------------- #
# run_update


def test_up_to_date_downloads_nothing_and_installs_nothing() -> None:
    net, runner = FakeNet(latest_routes("2.0.0")), FakeRunner()
    result = run_update("2.0.0", fetch=net, run=runner, which=which_of("uv"))
    assert result == UpdateResult("up_to_date", "2.0.0", "2.0.0", None)
    assert net.calls == [(LATEST_CHECKSUMS_URL, MAX_CHECKSUMS_BYTES)]
    assert runner.calls == []


def test_check_reports_an_available_release_without_installing() -> None:
    net, runner = FakeNet(latest_routes("2.1.0")), FakeRunner()
    result = run_update("2.0.0", check=True, fetch=net, run=runner, which=which_of("uv"))
    assert result.status == "available"
    assert (result.current, result.latest) == ("2.0.0", "2.1.0")
    assert len(net.calls) == 1
    assert runner.calls == []


def test_check_when_already_latest() -> None:
    net, runner = FakeNet(latest_routes("2.0.0")), FakeRunner()
    result = run_update("2.0.0", check=True, fetch=net, run=runner, which=which_of("uv"))
    assert result.status == "up_to_date"
    assert runner.calls == []


def test_update_installs_the_verified_wheel_with_uv() -> None:
    net, runner = FakeNet(latest_routes("2.1.0")), FakeRunner()
    result = run_update("2.0.0", fetch=net, run=runner, which=which_of("uv", "pipx"))
    assert result == UpdateResult("updated", "2.0.0", "2.1.0", "uv")
    assert net.calls[1] == (tag_url("2.1.0", wheel_name("2.1.0")), MAX_WHEEL_BYTES)
    [argv] = runner.calls
    assert argv[:4] == ["uv", "tool", "install", "--force"]
    assert Path(argv[4]).name == wheel_name("2.1.0")
    assert runner.payloads == [WHEEL_BYTES]
    # The temporary wheel is cleaned up once the installer has run.
    assert not Path(argv[4]).exists()


def test_update_falls_back_to_pipx() -> None:
    net, runner = FakeNet(latest_routes("2.1.0")), FakeRunner()
    result = run_update("2.0.0", fetch=net, run=runner, which=which_of("pipx"))
    assert result.installer == "pipx"
    assert runner.calls[0][:3] == ["pipx", "install", "--force"]


def test_update_without_any_installer() -> None:
    net, runner = FakeNet(latest_routes("2.1.0")), FakeRunner()
    with pytest.raises(LoopspecError) as excinfo:
        run_update("2.0.0", fetch=net, run=runner, which=which_of())
    assert error_code(excinfo) == "update_installer_missing"
    assert runner.calls == []


def test_tampered_wheel_is_never_installed() -> None:
    routes = latest_routes("2.1.0")
    routes[tag_url("2.1.0", wheel_name("2.1.0"))] = b"tampered"
    net, runner = FakeNet(routes), FakeRunner()
    with pytest.raises(LoopspecError) as excinfo:
        run_update("2.0.0", fetch=net, run=runner, which=which_of("uv"))
    assert error_code(excinfo) == "update_verify_failed"
    assert runner.calls == []


def test_missing_checksum_entry_fails_before_downloading_the_wheel() -> None:
    # The latest file names 2.1.0, but a pinned 2.2.0 release lists only its sdist.
    sdist_only = f"{'a' * 64}  loopspec-2.2.0.tar.gz\n".encode()
    net = FakeNet({tag_url("2.2.0", "checksums.txt"): sdist_only})
    runner = FakeRunner()
    with pytest.raises(LoopspecError) as excinfo:
        run_update("2.0.0", version="2.2.0", fetch=net, run=runner, which=which_of("uv"))
    assert error_code(excinfo) == "update_verify_failed"
    assert len(net.calls) == 1
    assert runner.calls == []


def test_pinned_version_uses_the_tag_url_and_reinstalls_the_same_version() -> None:
    routes = {
        tag_url("2.0.0", "checksums.txt"): checksums("2.0.0"),
        tag_url("2.0.0", wheel_name("2.0.0")): WHEEL_BYTES,
    }
    net, runner = FakeNet(routes), FakeRunner()
    result = run_update("2.0.0", version="2.0.0", fetch=net, run=runner, which=which_of("uv"))
    assert result.status == "updated"
    assert net.calls[0][0] == tag_url("2.0.0", "checksums.txt")
    assert len(runner.calls) == 1


@pytest.mark.parametrize("bad", ["1.0;rm -rf /", "../1.0.0", ""])
def test_invalid_pinned_version_makes_no_request(bad: str) -> None:
    net, runner = FakeNet({}), FakeRunner()
    with pytest.raises(LoopspecError) as excinfo:
        run_update("2.0.0", version=bad, fetch=net, run=runner, which=which_of("uv"))
    assert error_code(excinfo) == "update_invalid_version"
    assert net.calls == []


def test_hostile_latest_version_stops_before_the_wheel() -> None:
    hostile = f"{'a' * 64}  loopspec-$(id)-py3-none-any.whl\n".encode()
    net, runner = FakeNet({LATEST_CHECKSUMS_URL: hostile}), FakeRunner()
    with pytest.raises(LoopspecError) as excinfo:
        run_update("2.0.0", fetch=net, run=runner, which=which_of("uv"))
    assert error_code(excinfo) == "update_invalid_version"
    assert len(net.calls) == 1


def test_undecodable_checksums() -> None:
    net, runner = FakeNet({LATEST_CHECKSUMS_URL: b"\xff\xfe\xfa"}), FakeRunner()
    with pytest.raises(LoopspecError) as excinfo:
        run_update("2.0.0", fetch=net, run=runner, which=which_of("uv"))
    assert error_code(excinfo) == "update_fetch_failed"


def test_failing_installer() -> None:
    net, runner = FakeNet(latest_routes("2.1.0")), FakeRunner(returncode=1)
    with pytest.raises(LoopspecError) as excinfo:
        run_update("2.0.0", fetch=net, run=runner, which=which_of("uv"))
    assert error_code(excinfo) == "update_install_failed"


@pytest.mark.parametrize(
    ("exc", "code"),
    [
        (FileNotFoundError("uv"), "update_installer_missing"),
        (PermissionError("uv"), "update_install_failed"),
        (OSError("exec format error"), "update_install_failed"),
    ],
)
def test_installer_that_cannot_start_maps_to_an_error(exc: OSError, code: str) -> None:
    def broken_runner(argv: list[str]) -> int:
        raise exc

    net = FakeNet(latest_routes("2.1.0"))
    with pytest.raises(LoopspecError) as excinfo:
        run_update("2.0.0", fetch=net, run=broken_runner, which=which_of("uv"))
    assert error_code(excinfo) == code


def test_unwritable_temp_dir_maps_to_install_failed(monkeypatch: pytest.MonkeyPatch) -> None:
    def no_temp_dir(*args: object, **kwargs: object):
        raise OSError("No space left on device")

    monkeypatch.setattr(self_update.tempfile, "TemporaryDirectory", no_temp_dir)
    net, runner = FakeNet(latest_routes("2.1.0")), FakeRunner()
    with pytest.raises(LoopspecError) as excinfo:
        run_update("2.0.0", fetch=net, run=runner, which=which_of("uv"))
    assert error_code(excinfo) == "update_install_failed"
    assert runner.calls == []


def test_check_with_a_pinned_version() -> None:
    routes = {tag_url("1.9.0", "checksums.txt"): checksums("1.9.0")}
    net, runner = FakeNet(routes), FakeRunner()
    result = run_update("2.0.0", version="1.9.0", check=True, fetch=net, run=runner)
    assert (result.status, result.latest) == ("available", "1.9.0")
    assert len(net.calls) == 1
    assert runner.calls == []


# --------------------------------------------------------------------------- #
# Ordering, beta tracking and tag <-> version mapping


@pytest.mark.parametrize("check", [False, True])
def test_default_never_downgrades_an_installed_beta(check: bool) -> None:
    net, runner = FakeNet(latest_routes("1.1.3")), FakeRunner()
    result = run_update("1.1.4b0", check=check, fetch=net, run=runner, which=which_of("uv"))
    assert result == UpdateResult("up_to_date", "1.1.4b0", "1.1.3", None)
    assert net.calls == [(LATEST_CHECKSUMS_URL, MAX_CHECKSUMS_BYTES)]
    assert runner.calls == []


def test_default_never_downgrades_a_newer_stable() -> None:
    net, runner = FakeNet(latest_routes("1.1.3")), FakeRunner()
    result = run_update("1.2.0", fetch=net, run=runner, which=which_of("uv"))
    assert result.status == "up_to_date"
    assert len(net.calls) == 1
    assert runner.calls == []


def test_default_upgrades_to_a_newer_stable() -> None:
    net, runner = FakeNet(latest_routes("1.2.0")), FakeRunner()
    result = run_update("1.1.3", fetch=net, run=runner, which=which_of("uv"))
    assert result == UpdateResult("updated", "1.1.3", "1.2.0", "uv")
    assert net.calls[1] == (release_url("v1.2.0", wheel_name("1.2.0")), MAX_WHEEL_BYTES)
    assert runner.payloads == [WHEEL_BYTES]


def test_default_moves_an_installed_beta_on_to_the_next_stable() -> None:
    net, runner = FakeNet(latest_routes("1.2.0")), FakeRunner()
    result = run_update("1.1.4b0", fetch=net, run=runner, which=which_of("uv"))
    assert result == UpdateResult("updated", "1.1.4b0", "1.2.0", "uv")


@pytest.mark.parametrize("marked_latest", ["1.1.4b0", "1.1.4rc1", "1.1.4.post1"])
def test_default_refuses_a_non_stable_latest(marked_latest: str) -> None:
    net, runner = FakeNet(latest_routes(marked_latest)), FakeRunner()
    with pytest.raises(LoopspecError, match="not a stable release") as excinfo:
        run_update("1.1.3", fetch=net, run=runner, which=which_of("uv"))
    assert error_code(excinfo) == "update_fetch_failed"
    assert len(net.calls) == 1 and runner.payloads == []


def test_unparsable_installed_version_counts_as_older() -> None:
    net, runner = FakeNet(latest_routes("1.2.0")), FakeRunner()
    result = run_update("0+unknown", fetch=net, run=runner, which=which_of("uv"))
    assert result.status == "updated"


def test_beta_picks_the_newest_tag_and_downloads_from_the_beta_tag() -> None:
    junk = ['v1.1.4-evil"', "v9..9", "v1.1.9-beta1", "v1.1.9b0", "v1.1.9-rc", "v9.9.9-my-branch"]
    body = feed("v1.1.3", "v1.1.4-beta", *junk, "v1.1.2")
    routes = {RELEASES_FEED_URL: body, **tagged_routes("v1.1.4-beta", "1.1.4b0")}
    net, runner = FakeNet(routes), FakeRunner()
    result = run_update("1.1.3", beta=True, fetch=net, run=runner, which=which_of("uv"))
    assert result == UpdateResult("updated", "1.1.3", "1.1.4b0", "uv")
    assert net.calls == [
        (RELEASES_FEED_URL, MAX_FEED_BYTES),
        (release_url("v1.1.4-beta", "checksums.txt"), MAX_CHECKSUMS_BYTES),
        (release_url("v1.1.4-beta", "loopspec-1.1.4b0-py3-none-any.whl"), MAX_WHEEL_BYTES),
    ]
    assert runner.payloads == [WHEEL_BYTES]


class GoneNet(FakeNet):
    """Like FakeNet, but the listed URLs answer HTTP 404, as a release not published yet."""

    def __init__(self, routes: dict[str, bytes], gone: set[str]) -> None:
        super().__init__(routes)
        self.gone = gone

    def __call__(self, url: str, max_bytes: int) -> bytes:
        if url in self.gone:
            self.calls.append((url, max_bytes))
            raise self_update.UpdateReleaseNotFoundError(f"HTTP 404 for {url}")
        return super().__call__(url, max_bytes)


def test_beta_falls_back_when_the_newest_tag_has_no_release_yet() -> None:
    body = feed("v1.1.5-beta", "v1.1.4-beta", "v1.1.3")
    routes = {RELEASES_FEED_URL: body, **tagged_routes("v1.1.4-beta", "1.1.4b0")}
    gone = {release_url("v1.1.5-beta", "checksums.txt")}
    net, runner = GoneNet(routes, gone), FakeRunner()
    result = run_update("1.1.3", beta=True, fetch=net, run=runner, which=which_of("uv"))
    assert result == UpdateResult("updated", "1.1.3", "1.1.4b0", "uv")
    assert [url for url, _ in net.calls][:3] == [
        RELEASES_FEED_URL,
        release_url("v1.1.5-beta", "checksums.txt"),
        release_url("v1.1.4-beta", "checksums.txt"),
    ]


class FailingNet(FakeNet):
    """Like FakeNet, but the listed URLs fail for a reason other than a missing release."""

    def __init__(self, routes: dict[str, bytes], failing: set[str]) -> None:
        super().__init__(routes)
        self.failing = failing

    def __call__(self, url: str, max_bytes: int) -> bytes:
        if url in self.failing:
            self.calls.append((url, max_bytes))
            raise self_update.UpdateFetchFailedError(f"could not download {url} (HTTP 503)")
        return super().__call__(url, max_bytes)


def test_beta_stops_on_a_real_failure_of_the_newest_release() -> None:
    body = feed("v1.1.5-beta", "v1.1.4-beta")
    newest = release_url("v1.1.5-beta", "checksums.txt")
    net = FailingNet({RELEASES_FEED_URL: body, **tagged_routes("v1.1.4-beta", "1.1.4b0")}, {newest})
    with pytest.raises(LoopspecError, match="HTTP 503") as excinfo:
        run_update("1.1.4b0", beta=True, fetch=net, run=FakeRunner(), which=which_of("uv"))
    assert error_code(excinfo) == "update_fetch_failed"
    assert [url for url, _ in net.calls] == [RELEASES_FEED_URL, newest]


def test_beta_stops_on_an_undecodable_checksums_of_the_newest_release() -> None:
    body = feed("v1.1.5-beta", "v1.1.4-beta")
    newest = release_url("v1.1.5-beta", "checksums.txt")
    routes = {RELEASES_FEED_URL: body, newest: b"\xff\xfe"}
    net = FakeNet({**routes, **tagged_routes("v1.1.4-beta", "1.1.4b0")})
    with pytest.raises(LoopspecError, match="not UTF-8") as excinfo:
        run_update("1.1.4b0", beta=True, fetch=net, run=FakeRunner(), which=which_of("uv"))
    assert error_code(excinfo) == "update_fetch_failed"
    assert [url for url, _ in net.calls] == [RELEASES_FEED_URL, newest]


def test_beta_gives_up_after_the_candidate_limit() -> None:
    tags = ["v1.1.9-beta", "v1.1.8-beta", "v1.1.7-beta", "v1.1.6-beta"]
    gone = {release_url(tag, "checksums.txt") for tag in tags}
    net = GoneNet({RELEASES_FEED_URL: feed(*tags)}, gone)
    with pytest.raises(LoopspecError) as excinfo:
        run_update("1.1.3", beta=True, fetch=net, run=FakeRunner(), which=which_of("uv"))
    assert error_code(excinfo) == "update_fetch_failed"
    assert len(net.calls) == 1 + self_update.MAX_FEED_CANDIDATES


def test_beta_picks_the_stable_release_when_it_is_newest() -> None:
    body = feed("v1.2.0", "v1.1.5-beta", "v1.1.4-beta", "v1.1.3")
    routes = {RELEASES_FEED_URL: body, **tagged_routes("v1.2.0", "1.2.0")}
    net, runner = FakeNet(routes), FakeRunner()
    result = run_update("1.1.5b0", beta=True, fetch=net, run=runner, which=which_of("uv"))
    assert result == UpdateResult("updated", "1.1.5b0", "1.2.0", "uv")
    assert net.calls[-1][0] == release_url("v1.2.0", wheel_name("1.2.0"))


def test_beta_check_reports_a_newer_beta_without_installing() -> None:
    routes = {
        RELEASES_FEED_URL: feed("v1.1.4-beta", "v1.1.3"),
        **tagged_routes("v1.1.4-beta", "1.1.4b0"),
    }
    net, runner = FakeNet(routes), FakeRunner()
    result = run_update("1.1.3", beta=True, check=True, fetch=net, run=runner)
    assert result == UpdateResult("available", "1.1.3", "1.1.4b0", None)
    assert len(net.calls) == 2
    assert runner.calls == []


def test_beta_never_downgrades() -> None:
    routes = {RELEASES_FEED_URL: feed("v1.1.4-beta"), **tagged_routes("v1.1.4-beta", "1.1.4b0")}
    net, runner = FakeNet(routes), FakeRunner()
    result = run_update("1.1.4b0", beta=True, fetch=net, run=runner, which=which_of("uv"))
    assert result == UpdateResult("up_to_date", "1.1.4b0", "1.1.4b0", None)
    assert len(net.calls) == 2
    assert runner.calls == []


@pytest.mark.parametrize(
    "body",
    [
        b"",
        feed(),
        feed('v1.1.4-evil"', "v9..9", "v1.1.4b0", "v1.1.4-beta1"),
        b'<a href="https://github.com/someone/else/releases/tag/v9.9.9">x</a>',
        b"\xff\xfe\xfa",
    ],
)
def test_beta_without_a_usable_tag_fails_to_fetch(body: bytes) -> None:
    net, runner = FakeNet({RELEASES_FEED_URL: body}), FakeRunner()
    with pytest.raises(LoopspecError) as excinfo:
        run_update("1.1.3", beta=True, fetch=net, run=runner, which=which_of("uv"))
    assert error_code(excinfo) == "update_fetch_failed"
    assert net.calls == [(RELEASES_FEED_URL, MAX_FEED_BYTES)]
    assert runner.calls == []


@pytest.mark.parametrize("pinned", ["1.1.4-beta", "1.1.4b0"])
def test_pinned_beta_downloads_by_its_tag(pinned: str) -> None:
    net, runner = FakeNet(tagged_routes("v1.1.4-beta", "1.1.4b0")), FakeRunner()
    result = run_update("1.2.0", version=pinned, fetch=net, run=runner, which=which_of("uv"))
    assert result == UpdateResult("updated", "1.2.0", "1.1.4b0", "uv")
    assert [url for url, _ in net.calls] == [
        release_url("v1.1.4-beta", "checksums.txt"),
        release_url("v1.1.4-beta", "loopspec-1.1.4b0-py3-none-any.whl"),
    ]


@pytest.mark.parametrize("pinned", ["1.1.4-beta1", "2.1.0rc1", "v1.1.4-beta"])
def test_pinned_version_must_be_a_release_shape(pinned: str) -> None:
    net = FakeNet({})
    with pytest.raises(LoopspecError) as excinfo:
        run_update("1.1.3", version=pinned, fetch=net, run=FakeRunner())
    assert error_code(excinfo) == "update_invalid_version"
    assert net.calls == []


@pytest.mark.parametrize(
    ("kwargs", "tag", "shipped"),
    [
        ({"version": "1.1.4-beta"}, "v1.1.4-beta", "1.1.5b0"),
        ({"version": "1.2.0"}, "v1.2.0", "1.1.4b0"),
        ({"beta": True}, "v1.1.4-beta", "1.1.4"),
    ],
)
def test_checksums_must_name_the_tags_version(kwargs: dict, tag: str, shipped: str) -> None:
    routes = {RELEASES_FEED_URL: feed("v1.1.4-beta"), **tagged_routes(tag, shipped)}
    net, runner = FakeNet(routes), FakeRunner()
    with pytest.raises(LoopspecError) as excinfo:
        run_update("1.1.3", fetch=net, run=runner, which=which_of("uv"), **kwargs)
    assert error_code(excinfo) == "update_verify_failed"
    assert net.calls[-1][0] == release_url(tag, "checksums.txt")
    assert runner.calls == []


def test_beta_and_version_cannot_be_combined() -> None:
    net, runner = FakeNet({}), FakeRunner()
    with pytest.raises(LoopspecError) as excinfo:
        run_update("1.1.3", version="1.2.0", beta=True, fetch=net, run=runner)
    assert error_code(excinfo) == "update_invalid_version"
    assert net.calls == []


def test_default_runner_runs_without_a_shell(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict = {}

    class Completed:
        returncode = 3

    def fake_run(argv, **kwargs):
        seen["argv"], seen["kwargs"] = argv, kwargs
        return Completed()

    monkeypatch.setattr(self_update.subprocess, "run", fake_run)
    sink = io.StringIO()
    assert self_update.default_runner(["uv", "x"], stdout=sink) == 3
    assert seen["argv"] == ["uv", "x"]
    assert seen["kwargs"]["stdout"] is sink
    assert not seen["kwargs"].get("shell")


# --------------------------------------------------------------------------- #
# https_fetch


class FakeResponse(io.BytesIO):
    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


class FakeOpener:
    def __init__(self, outcome: bytes | Exception) -> None:
        self.outcome = outcome
        self.requests: list[tuple[str, float | None]] = []

    def open(self, url: str, timeout: float | None = None) -> FakeResponse:
        self.requests.append((url, timeout))
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return FakeResponse(self.outcome)


def install_opener(monkeypatch: pytest.MonkeyPatch, opener: FakeOpener) -> None:
    monkeypatch.setattr(self_update, "_build_opener", lambda: opener)


def test_https_fetch_reads_the_body_with_a_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    opener = FakeOpener(b"hello")
    install_opener(monkeypatch, opener)
    assert https_fetch("https://example.test/a", 10) == b"hello"
    assert opener.requests == [("https://example.test/a", self_update.TIMEOUT_SECONDS)]


def test_https_fetch_enforces_the_size_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    install_opener(monkeypatch, FakeOpener(b"x" * 11))
    with pytest.raises(LoopspecError) as excinfo:
        https_fetch("https://example.test/a", 10)
    assert error_code(excinfo) == "update_fetch_failed"


@pytest.mark.parametrize("url", ["http://example.test/a", "file:///etc/passwd", "ftp://x/y"])
def test_https_fetch_refuses_non_https(monkeypatch: pytest.MonkeyPatch, url: str) -> None:
    opener = FakeOpener(b"never")
    install_opener(monkeypatch, opener)
    with pytest.raises(LoopspecError) as excinfo:
        https_fetch(url, 10)
    assert error_code(excinfo) == "update_fetch_failed"
    assert opener.requests == []


@pytest.mark.parametrize(
    "exc",
    [
        urllib.error.URLError("down"),
        urllib.error.HTTPError("https://x", 404, "Not Found", None, None),  # type: ignore[arg-type]
        TimeoutError(),
        OSError("reset"),
    ],
)
def test_https_fetch_maps_network_errors(monkeypatch: pytest.MonkeyPatch, exc: Exception) -> None:
    install_opener(monkeypatch, FakeOpener(exc))
    with pytest.raises(LoopspecError) as excinfo:
        https_fetch("https://example.test/a", 10)
    assert error_code(excinfo) == "update_fetch_failed"


def test_https_fetch_tells_a_missing_release_from_other_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    missing = urllib.error.HTTPError("https://x", 404, "Not Found", None, None)  # type: ignore[arg-type]
    install_opener(monkeypatch, FakeOpener(missing))
    with pytest.raises(self_update.UpdateReleaseNotFoundError):
        https_fetch("https://example.test/a", 10)
    broken = urllib.error.HTTPError("https://x", 503, "Unavailable", None, None)  # type: ignore[arg-type]
    install_opener(monkeypatch, FakeOpener(broken))
    with pytest.raises(LoopspecError) as excinfo:
        https_fetch("https://example.test/a", 10)
    assert not isinstance(excinfo.value, self_update.UpdateReleaseNotFoundError)
    assert error_code(excinfo) == "update_fetch_failed"


def test_redirects_may_not_leave_https() -> None:
    handler = self_update._HttpsOnlyRedirectHandler()
    request = urllib.request.Request("https://github.com/a")
    with pytest.raises(urllib.error.URLError):
        handler.redirect_request(request, None, 302, "Found", {}, "http://evil.test/a")
    followed = handler.redirect_request(
        request, None, 302, "Found", {}, "https://objects.githubusercontent.com/a"
    )
    assert followed is not None
    assert followed.full_url == "https://objects.githubusercontent.com/a"


# --------------------------------------------------------------------------- #
# CLI

cli = CliRunner()


def patch_run_update(monkeypatch: pytest.MonkeyPatch, outcome: UpdateResult | Exception):
    seen: dict = {}

    def fake(current: str, **kwargs):
        seen.update(kwargs, current=current)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    monkeypatch.setattr(self_update, "run_update", fake)
    return seen


def test_cli_help_lists_the_options() -> None:
    result = cli.invoke(app, ["update", "--help"])
    assert result.exit_code == 0
    # CI (GITHUB_ACTIONS / FORCE_COLOR) makes rich colour the help, splitting
    # "--version" into "-" and "-version" with ANSI codes; compare plain text.
    plain = re.sub(r"\x1b\[[0-9;]*m", "", result.stdout)
    for option in ("--version", "--beta", "--check", "--json"):
        assert option in plain


def test_cli_json_success(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = patch_run_update(monkeypatch, UpdateResult("updated", "2.0.0", "2.1.0", "uv"))
    result = cli.invoke(app, ["update", "--json", "--version", "2.1.0"])
    assert result.exit_code == 0
    assert json.loads(result.stdout) == {
        "status": "updated",
        "current": "2.0.0",
        "latest": "2.1.0",
        "installer": "uv",
    }
    assert seen["version"] == "2.1.0"
    assert seen["check"] is False
    assert seen["beta"] is False


def test_cli_json_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    patch_run_update(monkeypatch, self_update.UpdateFetchFailedError("could not reach x"))
    result = cli.invoke(app, ["update", "--json"])
    assert result.exit_code == 1
    data = json.loads(result.stdout)
    assert data["error"] == "update_fetch_failed"
    assert set(data) == {"error", "message", "fix"}


@pytest.mark.parametrize(
    ("outcome", "expected"),
    [
        (UpdateResult("up_to_date", "2.0.0", "2.0.0", None), "loopspec 2.0.0 is up to date."),
        (UpdateResult("available", "2.0.0", "2.1.0", None), "loopspec 2.1.0 is available"),
        (UpdateResult("updated", "2.0.0", "2.1.0", "pipx"), "Updated loopspec 2.0.0 -> 2.1.0"),
    ],
)
def test_cli_human_output(
    monkeypatch: pytest.MonkeyPatch, outcome: UpdateResult, expected: str
) -> None:
    seen = patch_run_update(monkeypatch, outcome)
    result = cli.invoke(app, ["update", "--check"])
    assert result.exit_code == 0
    assert expected in result.stdout
    assert seen["check"] is True


def test_cli_human_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    patch_run_update(monkeypatch, self_update.UpdateInstallerMissingError("no installer"))
    result = cli.invoke(app, ["update"])
    assert result.exit_code == 1
    assert "update_installer_missing" in result.stdout


def test_cli_json_sends_installer_output_to_stderr(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = patch_run_update(monkeypatch, UpdateResult("up_to_date", "2.0.0", "2.0.0", None))
    cli.invoke(app, ["update", "--json"])
    # CliRunner swaps sys.stderr during invoke, so check the binding, not the object.
    assert seen["run"].func is self_update.default_runner
    assert set(seen["run"].keywords) == {"stdout"}
    assert seen["run"].keywords["stdout"] is not None
    assert seen["on_download"] is None


def test_cli_human_mode_announces_the_download(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = patch_run_update(monkeypatch, UpdateResult("up_to_date", "2.0.0", "2.0.0", None))
    cli.invoke(app, ["update"])
    assert seen["run"] is self_update.default_runner
    assert callable(seen["on_download"])


def test_cli_rejects_an_invalid_version_as_json() -> None:
    result = cli.invoke(app, ["update", "--json", "--version", "1.0;id"])
    assert result.exit_code == 1
    assert json.loads(result.stdout)["error"] == "update_invalid_version"


def test_cli_check_with_pinned_version_suggests_the_pinned_command(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    patch_run_update(monkeypatch, UpdateResult("available", "2.0.0", "1.9.0", None))
    result = cli.invoke(app, ["update", "--check", "--version", "1.9.0"])
    assert "loopspec update --version 1.9.0" in result.stdout


def test_cli_check_with_beta_suggests_the_beta_command(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = patch_run_update(monkeypatch, UpdateResult("available", "1.1.3", "1.1.4b0", None))
    result = cli.invoke(app, ["update", "--check", "--beta"])
    assert result.exit_code == 0
    assert seen["beta"] is True
    assert seen["version"] is None
    assert "loopspec 1.1.4b0 is available" in result.stdout
    assert "Run `loopspec update --beta` to install it." in result.stdout


def test_cli_check_without_flags_suggests_the_plain_command(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    patch_run_update(monkeypatch, UpdateResult("available", "1.1.3", "1.2.0", None))
    result = cli.invoke(app, ["update", "--check"])
    assert "Run `loopspec update` to install it." in result.stdout


def test_cli_rejects_beta_with_version_as_json() -> None:
    result = cli.invoke(app, ["update", "--json", "--beta", "--version", "1.2.0"])
    assert result.exit_code == 1
    data = json.loads(result.stdout)
    assert data["error"] == "update_invalid_version"
    assert "--beta" in data["message"]
