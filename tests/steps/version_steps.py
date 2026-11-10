"""Steps for `loopspec version`."""

from __future__ import annotations

from collections.abc import Callable

from pytest_bdd import then, when

import loopspec
from tests.conftest import CliOutcome, LastCall
from tests.steps.common import outcome_of

RunApp = Callable[..., CliOutcome]


@when("用户以 JSON 模式查看版本")
def version_json(run_app: RunApp, last_call: LastCall) -> None:
    last_call.outcome = run_app("version", "--json")


@when("用户以普通模式查看版本")
def version_plain(run_app: RunApp, last_call: LastCall) -> None:
    last_call.outcome = run_app("version")


@then("输出的版本号等于已安装包的版本")
def version_matches_package(last_call: LastCall) -> None:
    assert outcome_of(last_call).data["version"] == loopspec.__version__


@then("标准输出是一行非空文字")
def single_non_empty_line(last_call: LastCall) -> None:
    output = outcome_of(last_call).output
    lines = output.strip().splitlines()
    assert len(lines) == 1 and lines[0].strip(), output
