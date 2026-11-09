"""Steps for `loopspec memory list/show`; topics are files under home/memory."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from pytest_bdd import given, parsers, then, when

from tests.conftest import CliOutcome, LastCall
from tests.steps.common import outcome_of

RunCli = Callable[..., CliOutcome]


def put(home: Path, topic: str, text: str) -> Path:
    path = home / "memory" / f"{topic}.md"
    path.parent.mkdir(exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


# --- given ----------------------------------------------------------------------------


@given(parsers.parse('记忆主题 "{topic}" 的内容含适用时机 "{hint}"'))
def topic_with_hint(home: Path, topic: str, hint: str) -> None:
    path = put(home, topic, f"# {topic} 经验\n\n适用时机：{hint}\n\n## 条目\n- 内容\n")
    assert path.is_file()


@given(parsers.parse('记忆目录中有非 Markdown 文件 "{name}"'))
def non_markdown_file(home: Path, name: str) -> None:
    (home / "memory").mkdir(exist_ok=True)
    (home / "memory" / name).write_text("x")


@given(parsers.parse('记忆目录中有主题 "{topics}"'))
def plain_topics(home: Path, topics: str) -> None:
    for topic in topics.split(","):
        assert put(home, topic, f"# {topic}\n\n{topic} 的正文\n").is_file()


# --- when -----------------------------------------------------------------------------


@when("用户列出记忆主题")
def list_topics(run_cli: RunCli, last_call: LastCall) -> None:
    last_call.outcome = run_cli("memory", "list")


@when("用户以 --all 列出记忆主题")
def list_all_topics(run_cli: RunCli, last_call: LastCall) -> None:
    last_call.outcome = run_cli("memory", "list", "--all")


@when(parsers.re(r'用户以 limit "(?P<limit>[^"]+)"、offset "(?P<offset>[^"]+)" 列出记忆主题'))
def list_page(run_cli: RunCli, last_call: LastCall, limit: str, offset: str) -> None:
    last_call.outcome = run_cli("memory", "list", "--limit", limit, "--offset", offset)


@when(parsers.re(r'用户以 offset "(?P<offset>[^"]+)" 列出记忆主题'))
def list_from_offset(run_cli: RunCli, last_call: LastCall, offset: str) -> None:
    last_call.outcome = run_cli("memory", "list", "--offset", offset)


@when(parsers.parse('用户查看记忆主题 "{topic}"'))
def show_topic(run_cli: RunCli, last_call: LastCall, topic: str) -> None:
    last_call.outcome = run_cli("memory", "show", topic)


# --- then -----------------------------------------------------------------------------


@then(parsers.re(r'记忆主题列表为 "(?P<topics>[^"]*)"'))
def topics_are(last_call: LastCall, topics: str) -> None:
    expected = topics.split(",") if topics else []
    assert [entry["topic"] for entry in outcome_of(last_call).data["topics"]] == expected


@then(parsers.parse('主题 "{topic}" 的提示为 "{hint}"'))
def topic_hint(last_call: LastCall, topic: str, hint: str) -> None:
    entry = next(e for e in outcome_of(last_call).data["topics"] if e["topic"] == topic)
    assert entry["hint"] == hint, entry


@then("输出中没有 ignored 字段")
def no_ignored(last_call: LastCall) -> None:
    assert "ignored" not in outcome_of(last_call).data


@then(parsers.parse('被忽略的条目 "{name}" 原因为 "{reason}"'))
def ignored_with_reason(last_call: LastCall, name: str, reason: str) -> None:
    data = outcome_of(last_call).data
    assert {"name": name, "reason": reason} in data["ignored"], data


@then(parsers.parse('返回的内容与主题 "{topic}" 文件完全一致'))
def content_matches(home: Path, last_call: LastCall, topic: str) -> None:
    payload = outcome_of(last_call).data
    assert payload["topic"] == topic
    assert payload["content"] == (home / "memory" / f"{topic}.md").read_text(encoding="utf-8")


@then(parsers.parse('输出字段 "{field}" 非空'))
def field_not_empty(last_call: LastCall, field: str) -> None:
    data = outcome_of(last_call).data
    assert data.get(field), data
