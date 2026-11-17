"""Steps for features/graph.feature: `loopspec graph` for Profiles and Plans."""

from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path

import pytest
from pytest_bdd import given, parsers, then, when
from typer.testing import CliRunner

from loopspec import workflow_graph
from loopspec.cli import app
from tests.conftest import CliOutcome, LastCall
from tests.steps.common import outcome_of
from tests.workflow_helpers import BUGFIX_FLOW, CHANGE, create_draft, new_change

HEADLESS: dict[str, str] = {}
LOCAL_DESKTOP = {"DISPLAY": ":0"}
SSH = {"SSH_CONNECTION": "10.0.0.1 50000 10.0.0.2 22", "DISPLAY": ":0"}


@pytest.fixture
def browser_calls(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Never start a real browser: record the URLs `loopspec graph` asks to open."""
    calls: list[str] = []

    def fake_open(url: str) -> bool:
        calls.append(url)
        return True

    monkeypatch.setattr(workflow_graph.webbrowser, "open", fake_open)
    return calls


@pytest.fixture
def graph_draft() -> dict:
    return {}


def run_graph(
    run_cli: Callable[..., CliOutcome],
    monkeypatch: pytest.MonkeyPatch,
    env: dict[str, str],
    *args: str,
) -> CliOutcome:
    for name in ("SSH_CONNECTION", "SSH_TTY", "DISPLAY", "WAYLAND_DISPLAY"):
        monkeypatch.delenv(name, raising=False)
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    # The browser rule depends on the platform; pin Linux so every machine behaves the same.
    monkeypatch.setattr(workflow_graph.sys, "platform", "linux")
    return run_cli("graph", *args, "--json")


def run_graph_text(
    home: Path, monkeypatch: pytest.MonkeyPatch, env: dict[str, str], *args: str
) -> CliOutcome:
    """The default, human-facing output: plain text, not JSON."""
    for name in ("SSH_CONNECTION", "SSH_TTY", "DISPLAY", "WAYLAND_DISPLAY"):
        monkeypatch.delenv(name, raising=False)
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setattr(workflow_graph.sys, "platform", "linux")
    result = CliRunner().invoke(app, ["graph", *args, "--home", str(home)])
    return CliOutcome(result.exit_code, {}, result.stdout)


def graph_html(last_call: LastCall) -> str:
    data = outcome_of(last_call).data
    assert "path" in data, data
    return Path(data["path"]).read_text(encoding="utf-8")


@given("隔离项目中有一个缺陷修复流程的草稿 Plan")
def bugfix_draft(home: Path, graph_draft: dict) -> None:
    new_change(home)
    graph_draft.update(create_draft(home, BUGFIX_FLOW))
    assert graph_draft["digest"]


@given("隔离项目中有一个还没有 Plan 的 Change")
def change_without_plan(home: Path) -> None:
    new_change(home)


@when(parsers.re(r'用户在无图形界面的终端为 Profile "(?P<name>[^"]+)" 生成依赖图'))
def graph_profile_headless(
    run_cli: Callable[..., CliOutcome],
    monkeypatch: pytest.MonkeyPatch,
    browser_calls: list[str],
    last_call: LastCall,
    name: str,
) -> None:
    last_call.outcome = run_graph(run_cli, monkeypatch, HEADLESS, "--profile", name)


@when("用户在无图形界面的终端为 Change 当前的 Plan 生成依赖图")
def graph_open_plan(
    run_cli: Callable[..., CliOutcome],
    monkeypatch: pytest.MonkeyPatch,
    browser_calls: list[str],
    last_call: LastCall,
) -> None:
    last_call.outcome = run_graph(run_cli, monkeypatch, HEADLESS, "-c", CHANGE)


@when(parsers.re(r'用户在无图形界面的终端为 Change 的 Plan "(?P<plan>[^"]+)" 生成依赖图'))
def graph_given_plan(
    run_cli: Callable[..., CliOutcome],
    monkeypatch: pytest.MonkeyPatch,
    browser_calls: list[str],
    last_call: LastCall,
    plan: str,
) -> None:
    last_call.outcome = run_graph(run_cli, monkeypatch, HEADLESS, "-c", CHANGE, "--plan", plan)


@when(parsers.re(r'用户在无图形界面的终端为 Change "(?P<change>[^"]+)" 的当前 Plan 生成依赖图'))
def graph_named_change(
    run_cli: Callable[..., CliOutcome],
    monkeypatch: pytest.MonkeyPatch,
    browser_calls: list[str],
    last_call: LastCall,
    change: str,
) -> None:
    last_call.outcome = run_graph(run_cli, monkeypatch, HEADLESS, "-c", change)


@when(parsers.re(r'用户在 SSH 远程会话中为 Profile "(?P<name>[^"]+)" 生成依赖图'))
def graph_over_ssh(
    run_cli: Callable[..., CliOutcome],
    monkeypatch: pytest.MonkeyPatch,
    browser_calls: list[str],
    last_call: LastCall,
    name: str,
) -> None:
    last_call.outcome = run_graph(run_cli, monkeypatch, SSH, "--profile", name)


@when(parsers.re(r'用户在有图形界面的本机为 Profile "(?P<name>[^"]+)" 生成依赖图'))
def graph_on_desktop(
    run_cli: Callable[..., CliOutcome],
    monkeypatch: pytest.MonkeyPatch,
    browser_calls: list[str],
    last_call: LastCall,
    name: str,
) -> None:
    last_call.outcome = run_graph(run_cli, monkeypatch, LOCAL_DESKTOP, "--profile", name)


@when(parsers.re(r'用户把 Profile "(?P<name>[^"]+)" 的依赖图写到 "(?P<target>[^"]+)"'))
def graph_to_output(
    run_cli: Callable[..., CliOutcome],
    monkeypatch: pytest.MonkeyPatch,
    browser_calls: list[str],
    last_call: LastCall,
    tmp_path: Path,
    name: str,
    target: str,
) -> None:
    last_call.outcome = run_graph(
        run_cli, monkeypatch, HEADLESS, "--profile", name, "--output", str(tmp_path / target)
    )


@when(parsers.re(r'用户在 SSH 远程会话中以文本输出为 Profile "(?P<name>[^"]+)" 生成依赖图'))
def graph_text_over_ssh(
    home: Path,
    monkeypatch: pytest.MonkeyPatch,
    browser_calls: list[str],
    last_call: LastCall,
    name: str,
) -> None:
    last_call.outcome = run_graph_text(home, monkeypatch, SSH, "--profile", name)


@when("用户以文本输出只用 --plan 生成依赖图")
def graph_text_error(
    home: Path,
    monkeypatch: pytest.MonkeyPatch,
    browser_calls: list[str],
    last_call: LastCall,
) -> None:
    last_call.outcome = run_graph_text(home, monkeypatch, HEADLESS, "--plan", "001")


@when("用户同时用 --profile 与 --change 生成依赖图")
def graph_both_targets(
    run_cli: Callable[..., CliOutcome],
    monkeypatch: pytest.MonkeyPatch,
    browser_calls: list[str],
    last_call: LastCall,
) -> None:
    last_call.outcome = run_graph(
        run_cli, monkeypatch, HEADLESS, "--profile", "bugfix", "-c", CHANGE
    )


@when("用户不指定 Profile 也不指定 Change 生成依赖图")
def graph_no_target(
    run_cli: Callable[..., CliOutcome],
    monkeypatch: pytest.MonkeyPatch,
    browser_calls: list[str],
    last_call: LastCall,
) -> None:
    last_call.outcome = run_graph(run_cli, monkeypatch, HEADLESS)


@when("用户只用 --plan 生成依赖图")
def graph_plan_without_change(
    run_cli: Callable[..., CliOutcome],
    monkeypatch: pytest.MonkeyPatch,
    browser_calls: list[str],
    last_call: LastCall,
) -> None:
    last_call.outcome = run_graph(run_cli, monkeypatch, HEADLESS, "--plan", "001")


@then(parsers.re(r'依赖图的可并行层包含 "(?P<layer>[0-9]+)"'))
def parallel_layer_included(last_call: LastCall, layer: str) -> None:
    data = outcome_of(last_call).data
    assert int(layer) in data["parallelLayers"], data


@then(parsers.re(r'依赖图 HTML 包含 "(?P<text>[^"]+)"'))
def html_contains(last_call: LastCall, text: str) -> None:
    assert text in graph_html(last_call)


@then(parsers.re(r"依赖图 HTML 包含 '(?P<text>[^']+)'"))
def html_contains_quoted(last_call: LastCall, text: str) -> None:
    assert text in graph_html(last_call)


@then("依赖图中没有任何节点带运行状态")
def no_node_status(last_call: LastCall) -> None:
    html = graph_html(last_call)
    assert 'class="node ' in html
    assert not re.search(r'class="node [^"]*status-', html)


@then(parsers.re(r'依赖图中节点 "(?P<node>[^"]+)" 的状态为 "(?P<state>[^"]+)"'))
def graph_node_state(last_call: LastCall, node: str, state: str) -> None:
    html = graph_html(last_call)
    pattern = rf'class="node [^"]*status-{re.escape(state)}" data-id="{re.escape(node)}"'
    assert re.search(pattern, html), node


@then("依赖图 HTML 包含草稿 Plan 的 digest")
def html_has_draft_digest(last_call: LastCall, graph_draft: dict) -> None:
    assert graph_draft["digest"] in graph_html(last_call)


@then(parsers.re(r'依赖图文件位于 workflow home 的 "(?P<relative>[^"]+)"'))
def graph_in_home_cache(last_call: LastCall, home: Path, relative: str) -> None:
    data = outcome_of(last_call).data
    assert Path(data["path"]) == (home / relative).resolve(), data
    assert (home / relative).is_file()


@then("输出的 url 是依赖图文件的 file:// 链接")
def url_is_file_link(last_call: LastCall) -> None:
    data = outcome_of(last_call).data
    assert data["url"] == Path(data["path"]).as_uri(), data
    assert data["url"].startswith("file://")
    assert Path(data["path"]).is_file()


@then("没有调用浏览器")
def browser_not_called(browser_calls: list[str]) -> None:
    assert browser_calls == []


@then("浏览器打开的正是输出的 url")
def browser_opened_url(last_call: LastCall, browser_calls: list[str]) -> None:
    assert browser_calls == [outcome_of(last_call).data["url"]]


@then(parsers.re(r'文件 "(?P<target>[^"]+)" 是依赖图 HTML'))
def output_is_graph(last_call: LastCall, tmp_path: Path, target: str) -> None:
    path = tmp_path / target
    assert Path(outcome_of(last_call).data["path"]) == path.resolve()
    assert path.read_text(encoding="utf-8").startswith("<!DOCTYPE html>")


@then("没有写出任何依赖图文件")
def no_graph_written(home: Path) -> None:
    assert not (home / ".cache" / "graph").exists()


@then(parsers.re(r'文本输出包含 "(?P<text>[^"]+)"'))
def text_output_contains(last_call: LastCall, text: str) -> None:
    assert text in outcome_of(last_call).output, outcome_of(last_call).output


@then(parsers.re(r"命令以退出码 (?P<code>[0-9]+) 结束"))
def command_exit_code(last_call: LastCall, code: str) -> None:
    assert outcome_of(last_call).code == int(code), outcome_of(last_call).output
