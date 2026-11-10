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


# --- when: the Agent edits memory files directly (the CLI only reads them) -------------


@when(
    parsers.re(
        r'Agent 新建记忆主题 "(?P<topic>[^"]+)"，标题为 "(?P<title>[^"]+)"、'
        r'适用时机为 "(?P<hint>[^"]+)"'
    )
)
def agent_creates_topic(home: Path, topic: str, title: str, hint: str) -> None:
    path = home / "memory" / f"{topic}.md"
    assert not path.exists(), path
    put(home, topic, f"# {title}\n\n适用时机：{hint}\n\n## 条目\n- 首条经验\n")


@when(parsers.re(r'Agent 新建记忆主题 "(?P<topic>[^"]+)"，内容为 "(?P<entry>[^"]+)"'))
def agent_creates_topic_with_entry(home: Path, topic: str, entry: str) -> None:
    path = home / "memory" / f"{topic}.md"
    assert not path.exists(), path
    put(home, topic, f"# {topic}\n\n{entry}\n")


@when(
    parsers.re(
        r'Agent 把主题 "(?P<topic>[^"]+)" 的适用时机改为 "(?P<hint>[^"]+)" '
        r'并追加条目 "(?P<entry>[^"]+)"'
    )
)
def agent_updates_topic(home: Path, topic: str, hint: str, entry: str) -> None:
    path = home / "memory" / f"{topic}.md"
    lines = path.read_text(encoding="utf-8").splitlines()
    index = next(i for i, line in enumerate(lines) if line.startswith("适用时机："))
    lines[index] = f"适用时机：{hint}"
    path.write_text("\n".join([*lines, entry]) + "\n", encoding="utf-8")


@when(parsers.re(r'Agent 在主题 "(?P<topic>[^"]+)" 末尾追加 "(?P<entry>[^"]+)"'))
def agent_appends_entry(home: Path, topic: str, entry: str) -> None:
    path = home / "memory" / f"{topic}.md"
    with path.open("a", encoding="utf-8") as handle:
        handle.write(f"{entry}\n")


@when(parsers.parse('Agent 在记忆目录新建文件 "{name}"'))
def agent_creates_file(home: Path, name: str) -> None:
    (home / "memory").mkdir(exist_ok=True)
    (home / "memory" / name).write_text("# 不该成为主题\n", encoding="utf-8")


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


@then(parsers.parse('主题 "{topic}" 的标题为 "{title}"'))
def topic_title(last_call: LastCall, topic: str, title: str) -> None:
    entry = next(e for e in outcome_of(last_call).data["topics"] if e["topic"] == topic)
    assert entry["title"] == title, entry


@then(parsers.parse('主题 "{topic}" 的大小与文件字节数一致'))
def topic_bytes(home: Path, last_call: LastCall, topic: str) -> None:
    entry = next(e for e in outcome_of(last_call).data["topics"] if e["topic"] == topic)
    assert entry["bytes"] == (home / "memory" / f"{topic}.md").stat().st_size, entry


@then(parsers.parse('返回的内容包含 "{text}"'))
def content_contains(last_call: LastCall, text: str) -> None:
    assert text in outcome_of(last_call).data["content"]


@then(parsers.parse('返回的内容不包含 "{text}"'))
def content_lacks(last_call: LastCall, text: str) -> None:
    assert text not in outcome_of(last_call).data["content"]


@then("Change 状态中没有 core")
def status_without_core(last_call: LastCall) -> None:
    core = outcome_of(last_call).data["memory"]["core"]
    assert core["present"] is False, core


@then(parsers.parse('Change 状态内联的 core 包含 "{text}"'))
def status_core_contains(last_call: LastCall, text: str) -> None:
    core = outcome_of(last_call).data["memory"]["core"]
    assert core["present"] is True and text in core["content"], core


@then(parsers.parse('Change 状态内联的 core 与主题 "{topic}" 文件完全一致'))
def status_core_matches(home: Path, last_call: LastCall, topic: str) -> None:
    core = outcome_of(last_call).data["memory"]["core"]
    assert core["truncated"] is False, core
    assert core["content"] == (home / "memory" / f"{topic}.md").read_text(encoding="utf-8")


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
