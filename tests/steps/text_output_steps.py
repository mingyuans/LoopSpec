"""Steps for features/text_output.feature: text reports by default, JSON with --json."""

from __future__ import annotations

import json
import re
from pathlib import Path

from pytest_bdd import parsers, then, when
from typer.testing import CliRunner

from loopspec.cli import app
from tests.conftest import CliOutcome, LastCall
from tests.steps.common import outcome_of
from tests.workflow_helpers import CHANGE, loaded

runner = CliRunner()


def _call(home: Path, last_call: LastCall, *args: str) -> None:
    result = runner.invoke(app, [*args, "--home", str(home)])
    data: dict = {}
    if "--json" in args and result.stdout.strip():
        data = json.loads(result.stdout)
    last_call.outcome = CliOutcome(result.exit_code, data, output=result.stdout)


@when(parsers.re(r'以默认格式获取节点 "(?P<node>[^"]+)" 的执行指令'))
def text_instructions(home: Path, last_call: LastCall, node: str) -> None:
    _call(home, last_call, "node", "instructions", "-c", CHANGE, "-n", node)


@when(parsers.re(r'以 --json 获取节点 "(?P<node>[^"]+)" 的执行指令'))
def json_instructions(home: Path, last_call: LastCall, node: str) -> None:
    _call(home, last_call, "node", "instructions", "-c", CHANGE, "-n", node, "--json")


@when(parsers.re(r'以默认格式查看不存在的需求 "(?P<change>[^"]+)" 的 Plan'))
def text_missing_plan(home: Path, last_call: LastCall, change: str) -> None:
    _call(home, last_call, "plan", "show", "-c", change)


@then(parsers.re(r'输出是以 "(?P<header>[^"]+)" 开头的文本报告'))
def starts_with(last_call: LastCall, header: str) -> None:
    text = outcome_of(last_call).output
    assert text.startswith(header + "\n")
    assert "\x1b" not in text
    try:
        json.loads(text)
    except json.JSONDecodeError:
        return
    raise AssertionError("the default output must not be JSON")


@then(
    parsers.re(
        r'文本中有 "(?P<first>[A-Z]+)" 与 "(?P<second>[A-Z]+)" 两节，'
        r"正文在 begin/end 行之间逐行缩进四个空格且行数一致"
    )
)
def quoted_sections(home: Path, last_call: LastCall, first: str, second: str) -> None:
    text = outcome_of(last_call).output
    for name in (first, second):
        body = text.split(f"\n=== {name} ===\n", 1)[1].split("\n=== ", 1)[0]
        label = name.lower()
        begin = re.search(rf"(?m)^--- begin {label} \((\d+) lines?\) ---$", body)
        assert begin, name
        quoted = body[begin.end() + 1 :].split(f"\n--- end {label} ---", 1)[0].split("\n")
        assert len(quoted) == int(begin[1]), name
        assert quoted and all(line.startswith("    ") for line in quoted), name
    assert "\\n" not in text


@then(parsers.re(r'文本中有 "(?P<key>\w+)" 字段，值为活动 Plan 目录下的 "(?P<relative>[^"]+)"'))
def key_value(home: Path, last_call: LastCall, key: str, relative: str) -> None:
    expected = str(loaded(home).root / relative)
    text = outcome_of(last_call).output
    assert re.search(rf"(?m)^{key}:\s+{re.escape(expected)}$", text), text


@then(parsers.re(r'退出码为 1，输出是 "=== ERROR ===" 报告且错误码为 "(?P<code>[a-z_]+)"'))
def error_report(last_call: LastCall, code: str) -> None:
    outcome = outcome_of(last_call)
    assert outcome.code == 1
    assert outcome.output.startswith("=== ERROR ===\n")
    assert re.search(rf"(?m)^error:\s+{code}$", outcome.output)
