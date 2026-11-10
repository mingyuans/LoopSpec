"""Steps for `loopspec update`; `run_update` is stubbed so nothing goes online."""

from __future__ import annotations

import functools
from collections.abc import Callable
from typing import Any

import pytest
from pytest_bdd import given, parsers, then, when

from loopspec import self_update
from loopspec.self_update import UpdateResult
from tests.conftest import CliOutcome, LastCall
from tests.steps.common import outcome_of

RunApp = Callable[..., CliOutcome]


@pytest.fixture
def update_calls() -> list[dict[str, Any]]:
    """Keyword arguments of every call to the stubbed `run_update`, in order."""
    return []


@pytest.fixture
def fetched_urls() -> list[str]:
    """URLs the real `run_update` tried to download, when only the network is stubbed."""
    return []


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
