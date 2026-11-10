"""Steps for features/update.feature; `run_update` or its network is stubbed, never online."""

from __future__ import annotations

import functools
import hashlib
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, parsers, then, when

from loopspec import self_update
from loopspec.self_update import (
    LATEST_CHECKSUMS_URL,
    RELEASES,
    RELEASES_FEED_URL,
    UpdateResult,
    package_version,
    release_tag,
)
from tests.conftest import CliOutcome, LastCall
from tests.steps.common import outcome_of

RunApp = Callable[..., CliOutcome]

WHEEL_BYTES = b"offline test wheel"


@dataclass
class ReleaseSite:
    """An offline GitHub Releases: canned bodies by URL, plus what got installed."""

    installed: str | None = None
    routes: dict[str, bytes] = field(default_factory=dict)
    #: File names of the wheels handed to the (fake) installer.
    installed_wheels: list[str] = field(default_factory=list)

    def publish(self, tag: str, *, latest: bool = False) -> str:
        """Serve `tag`'s checksums.txt and wheel; return the wheel's package version."""
        version = package_version(tag)
        wheel = f"loopspec-{version}-py3-none-any.whl"
        digest = hashlib.sha256(WHEEL_BYTES).hexdigest()
        body = f"{digest}  {wheel}\n".encode()
        self.routes[f"{RELEASES}/download/{tag}/checksums.txt"] = body
        self.routes[f"{RELEASES}/download/{tag}/{wheel}"] = WHEEL_BYTES
        if latest:
            self.routes[LATEST_CHECKSUMS_URL] = body
        return version


@pytest.fixture
def update_calls() -> list[dict[str, Any]]:
    """Keyword arguments of every call to the stubbed `run_update`, in order."""
    return []


@pytest.fixture
def fetched_urls() -> list[str]:
    """URLs the real `run_update` tried to download, when only the network is stubbed."""
    return []


@pytest.fixture
def release_site(monkeypatch: pytest.MonkeyPatch, fetched_urls: list[str]) -> ReleaseSite:
    """Run the real `run_update` against an offline release site and a fake installer."""

    site = ReleaseSite()

    def fetch(url: str, limit: int) -> bytes:
        fetched_urls.append(url)
        if url not in site.routes:
            raise self_update.UpdateFetchFailedError(f"offline test: nothing at {url}")
        body = site.routes[url]
        assert len(body) <= limit, url
        return body

    def install(argv: list[str]) -> int:
        site.installed_wheels.append(Path(argv[-1]).name)
        return 0

    def uv_only(name: str) -> str | None:
        return "/usr/bin/uv" if name == "uv" else None

    real = self_update.run_update

    def offline(current: str, **kwargs: Any) -> UpdateResult:
        kwargs.update(fetch=fetch, run=install, which=uv_only)
        return real(site.installed or current, **kwargs)

    monkeypatch.setattr(self_update, "run_update", offline)
    return site


def stub_run_update(
    monkeypatch: pytest.MonkeyPatch,
    calls: list[dict[str, Any]],
    outcome: UpdateResult | Exception,
) -> None:
    def fake(current: str, **kwargs: Any) -> UpdateResult:
        calls.append({**kwargs, "current": current})
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    monkeypatch.setattr(self_update, "run_update", fake)


@given(
    parsers.re(
        r'升级流程会把 "(?P<current>[^"]+)" 升级到 "(?P<latest>[^"]+)"，'
        r'安装器为 "(?P<installer>[^"]+)"'
    )
)
def update_will_succeed(
    monkeypatch: pytest.MonkeyPatch,
    update_calls: list[dict[str, Any]],
    current: str,
    latest: str,
    installer: str,
) -> None:
    stub_run_update(monkeypatch, update_calls, UpdateResult("updated", current, latest, installer))


@given("升级流程无法连接发布服务器")
def update_cannot_fetch(
    monkeypatch: pytest.MonkeyPatch, update_calls: list[dict[str, Any]]
) -> None:
    error = self_update.UpdateFetchFailedError("could not reach the release server")
    stub_run_update(monkeypatch, update_calls, error)


@given("升级流程的所有网络请求都会被记录并拦截")
def network_is_recorded(monkeypatch: pytest.MonkeyPatch, fetched_urls: list[str]) -> None:
    """Keep the real `run_update` (it owns version validation) but never let it go online."""

    def fetch(url: str, limit: int) -> bytes:
        fetched_urls.append(url)
        raise self_update.UpdateFetchFailedError(f"offline test: refused {url}")

    real = self_update.run_update
    monkeypatch.setattr(self_update, "run_update", functools.partial(real, fetch=fetch))


@given(parsers.re(r'升级流程报告 "(?P<current>[^"]+)" 已是最新版本'))
def update_is_current(
    monkeypatch: pytest.MonkeyPatch, update_calls: list[dict[str, Any]], current: str
) -> None:
    stub_run_update(monkeypatch, update_calls, UpdateResult("up_to_date", current, current, None))


@given(parsers.re(r'已安装的 loopspec 版本为 "(?P<version>[^"]+)"'))
def installed_version_is(release_site: ReleaseSite, version: str) -> None:
    assert self_update.validate_version(version) == version
    release_site.installed = version


@given(parsers.re(r'发布服务器的 Latest 正式版为 "(?P<version>[^"]+)"'))
def latest_stable_is(release_site: ReleaseSite, version: str) -> None:
    assert release_site.publish(release_tag(version), latest=True) == version
    assert not self_update.is_beta(version)


@given(parsers.re(r'发布服务器上有 tag 为 "(?P<tag>[^"]+)" 的 Release'))
def release_exists(release_site: ReleaseSite, tag: str) -> None:
    assert release_tag(release_site.publish(tag)) == tag


@given(parsers.re(r'Release 订阅源依次列出 tag "(?P<tags>[^"]+)"'))
def feed_lists_tags(release_site: ReleaseSite, tags: str) -> None:
    entries = "".join(
        f'<entry><link rel="alternate" type="text/html" '
        f'href="https://github.com/mingyuans/LoopSpec/releases/tag/{tag.strip()}"/></entry>\n'
        for tag in tags.split(",")
    )
    release_site.routes[RELEASES_FEED_URL] = f"<feed>\n{entries}</feed>\n".encode()
    assert entries.count("<entry>") == len(tags.split(","))


@when("用户以 JSON 模式跟踪 beta 升级")
def update_json_beta(run_app: RunApp, last_call: LastCall) -> None:
    last_call.outcome = run_app("update", "--json", "--beta")


@when(parsers.re(r'用户以 JSON 模式同时使用 --beta 和 --version "(?P<version>[^"]+)" 升级'))
def update_json_beta_and_version(run_app: RunApp, last_call: LastCall, version: str) -> None:
    last_call.outcome = run_app("update", "--json", "--beta", "--version", version)


@then("没有下载任何 wheel")
def no_wheel_fetched(fetched_urls: list[str]) -> None:
    assert not [url for url in fetched_urls if url.endswith(".whl")], fetched_urls


@then("没有安装任何版本")
def nothing_installed(release_site: ReleaseSite) -> None:
    assert release_site.installed_wheels == []


@then(parsers.re(r'wheel 从 tag "(?P<tag>[^"]+)" 的 Release 下载'))
def wheel_from_tag(fetched_urls: list[str], tag: str) -> None:
    wheels = [url for url in fetched_urls if url.endswith(".whl")]
    assert len(wheels) == 1, fetched_urls
    assert wheels[0].startswith(f"{RELEASES}/download/{tag}/"), wheels


@then(parsers.re(r'安装器安装了 "(?P<wheel>[^"]+)"'))
def installer_got(release_site: ReleaseSite, wheel: str) -> None:
    assert release_site.installed_wheels == [wheel]


@when(parsers.re(r'用户以 JSON 模式升级到版本 "(?P<version>[^"]+)"'))
def update_to_version(run_app: RunApp, last_call: LastCall, version: str) -> None:
    last_call.outcome = run_app("update", "--json", "--version", version)


@when("用户以 JSON 模式升级")
def update_json(run_app: RunApp, last_call: LastCall) -> None:
    last_call.outcome = run_app("update", "--json")


@when("用户仅检查是否有新版本")
def update_check(run_app: RunApp, last_call: LastCall) -> None:
    last_call.outcome = run_app("update", "--check")


@then(parsers.parse('升级流程收到的目标版本为 "{version}"'))
def stub_got_version(update_calls: list[dict[str, Any]], version: str) -> None:
    assert len(update_calls) == 1, update_calls
    assert update_calls[0]["version"] == version
    assert update_calls[0]["check"] is False


@then("错误输出只包含 error、message、fix 三个字段")
def error_keys_exact(last_call: LastCall) -> None:
    data = outcome_of(last_call).data
    assert set(data) == {"error", "message", "fix"}, data


@then("没有发出任何网络请求")
def nothing_fetched(fetched_urls: list[str]) -> None:
    assert fetched_urls == []


@then(parsers.parse('标准输出包含 "{text}"'))
def stdout_contains(last_call: LastCall, text: str) -> None:
    output = outcome_of(last_call).output
    assert text in output, output


@then("升级流程以仅检查模式被调用")
def stub_called_in_check_mode(update_calls: list[dict[str, Any]]) -> None:
    assert len(update_calls) == 1 and update_calls[0]["check"] is True, update_calls
