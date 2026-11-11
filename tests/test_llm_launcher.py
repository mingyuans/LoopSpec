"""Unit tests for the unified LLM launcher; no model is ever started here."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from tests import llm_launcher
from tests.llm_launcher import (
    DEFAULT_MODEL,
    LAUNCHERS,
    AgentRun,
    ClaudeCliLauncher,
    LaunchConfig,
    LaunchConfigError,
    LaunchRequest,
    LaunchTimeout,
    launch_llm,
)


def request(tmp_path: Path, resume: str | None = None) -> LaunchRequest:
    return LaunchRequest(tmp_path, "/loopspec-new 做点事", tmp_path / "run.jsonl", resume)


# --- configuration ---------------------------------------------------------------------


def test_defaults_name_a_launcher_and_a_non_opus_model() -> None:
    config = LaunchConfig.from_env({})
    assert config == LaunchConfig()
    assert config.launcher == "claude-cli" and config.model == DEFAULT_MODEL == "claude-sonnet-5-5"


def test_settings_come_from_the_environment_by_name() -> None:
    config = LaunchConfig.from_env(
        {
            "LOOPSPEC_LLM_MODEL": "claude-haiku-5-5",
            "LOOPSPEC_LLM_BUDGET_USD": "0.5",
            "LOOPSPEC_LLM_MAX_TURNS": "12",
            "LOOPSPEC_LLM_TIMEOUT": "90",
        }
    )
    assert (config.model, config.max_budget_usd, config.max_turns, config.timeout_s) == (
        "claude-haiku-5-5",
        0.5,
        12,
        90,
    )


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("LOOPSPEC_LLM_BUDGET_USD", "-1"),
        ("LOOPSPEC_LLM_BUDGET_USD", "lots"),
        ("LOOPSPEC_LLM_MAX_TURNS", "0"),
        ("LOOPSPEC_LLM_TIMEOUT", "1.5"),
        ("LOOPSPEC_LLM_MODEL", "sonnet; rm -rf /"),
        ("LOOPSPEC_LLM_MODEL", "claude-opus-5-5"),
        ("LOOPSPEC_LLM_MODEL", "default"),
        ("LOOPSPEC_LLM_MODEL", "opus"),
        ("LOOPSPEC_LLM_MODEL", "best"),
        ("LOOPSPEC_LLM_MODEL", "-x"),
        ("LOOPSPEC_LLM_MODEL", "claude-sonnet-５-5"),
        ("LOOPSPEC_LLM_LAUNCHER", "no-such-launcher"),
    ],
)
def test_invalid_settings_name_the_variable_but_never_echo_its_value(name: str, value: str) -> None:
    with pytest.raises(LaunchConfigError) as excinfo:
        LaunchConfig.from_env({name: value})
    assert name in str(excinfo.value)
    assert value not in str(excinfo.value)


# --- claude-cli: argv ------------------------------------------------------------------


def test_claude_argv_always_passes_the_model_and_isolates_the_session(tmp_path: Path) -> None:
    argv = ClaudeCliLauncher().argv(request(tmp_path), LaunchConfig())
    assert argv[:3] == ["claude", "-p", "/loopspec-new 做点事"]
    assert argv[argv.index("--model") + 1] == "claude-sonnet-5-5"
    assert argv[argv.index("--setting-sources") + 1] == "project"
    assert "--strict-mcp-config" in argv
    assert argv[argv.index("--permission-mode") + 1] == "dontAsk"
    assert argv[argv.index("--output-format") + 1] == "stream-json"
    assert argv[argv.index("--allowedTools") + 1 :] == list(ClaudeCliLauncher.allowed_tools)
    assert "--resume" not in argv
    for forbidden in ("--dangerously-skip-permissions", "--bare"):
        assert forbidden not in argv


def test_claude_argv_carries_limits_and_resume(tmp_path: Path) -> None:
    config = LaunchConfig(model="claude-haiku-5-5", max_budget_usd=0.25, max_turns=7)
    argv = ClaudeCliLauncher().argv(request(tmp_path, resume="sess-1"), config)
    assert argv[argv.index("--model") + 1] == "claude-haiku-5-5"
    assert argv[argv.index("--max-turns") + 1] == "7"
    assert argv[argv.index("--max-budget-usd") + 1] == "0.25"
    assert argv[argv.index("--resume") + 1] == "sess-1"


def test_bash_runs_loopspec_only_and_file_tools_stay_in_the_project() -> None:
    allowed = ClaudeCliLauncher.allowed_tools
    bash_rules = [rule for rule in allowed if rule.startswith("Bash")]
    assert bash_rules == [f"Bash(loopspec {sub}:*)" for sub in llm_launcher.LOOPSPEC_SUBCOMMANDS]
    for refused in ("init", "update", "hook", "registry", "version"):
        assert f"Bash(loopspec {refused}:*)" not in allowed  # hook runs only via Claude
    assert "Bash(loopspec:*)" not in allowed
    file_rules = [rule for rule in allowed if not rule.startswith("Bash")]
    assert file_rules and all(re.fullmatch(r"\w+\(\./\*\*\)", rule) for rule in file_rules)
    for tool in ("Read", "Write", "Edit", "Glob", "Grep"):
        assert tool not in allowed  # a bare tool name would allow every path
        assert f"{tool}(~/**)" in ClaudeCliLauncher.disallowed_tools


def test_claude_argv_denies_the_home_directory_and_explains_the_harness(tmp_path: Path) -> None:
    argv = ClaudeCliLauncher().argv(request(tmp_path), LaunchConfig())
    denied = argv[argv.index("--disallowedTools") + 1 : argv.index("--allowedTools")]
    assert denied == list(ClaudeCliLauncher.disallowed_tools)
    prompt = argv[argv.index("--append-system-prompt") + 1]
    assert "single `loopspec" in prompt and "Write" in prompt


def test_child_environment_passes_allow_listed_names_only() -> None:
    environ = {
        "HOME": "h", "PATH": "/usr/bin", "LANG": "C", "LC_ALL": "C", "TMPDIR": "t",
        "CLAUDE_CONFIG_DIR": "c", "ANTHROPIC_BASE_URL": "a",
        "AWS_SECRET_ACCESS_KEY": "x", "GITHUB_TOKEN": "y", "OPENAI_API_KEY": "z",
    }  # fmt: skip
    env = llm_launcher.child_environment(environ)
    assert set(env) == {
        "HOME", "PATH", "LANG", "LC_ALL", "TMPDIR", "CLAUDE_CONFIG_DIR", "ANTHROPIC_BASE_URL",
        "LOOPSPEC_LLM_REAL_LOOPSPEC",
    }  # fmt: skip
    assert env["PATH"] == f"{llm_launcher.GUARD_BIN}:{llm_launcher.VENV_BIN}:/usr/bin"
    assert env["LOOPSPEC_LLM_REAL_LOOPSPEC"] == str(llm_launcher.VENV_BIN / "loopspec")


# --- claude-cli: stream parsing --------------------------------------------------------


def stream(*events: dict[str, Any]) -> list[str]:
    return [json.dumps(event) for event in events]


def tool_use(name: str, **inputs: str) -> dict[str, Any]:
    content = [{"type": "tool_use", "name": name, "input": inputs}]
    return {"type": "assistant", "message": {"content": content}}


RESULT = {
    "type": "result",
    "subtype": "success",
    "session_id": "sess-9",
    "num_turns": 3,
    "total_cost_usd": 0.12,
    "is_error": False,
    "result": "请确认这个草稿",
    "permission_denials": [{"tool_name": "Bash"}],
}


def test_parse_collects_commands_tools_and_the_result() -> None:
    lines = [
        *stream(tool_use("Bash", command="loopspec change new X"), tool_use("Read", path="a")),
        "not json",
        "[1, 2]",
        *stream(tool_use("Bash", command="loopspec plan show -c X -p 001"), RESULT),
    ]
    fields = ClaudeCliLauncher.parse(lines)
    assert fields["bash_commands"] == ["loopspec change new X", "loopspec plan show -c X -p 001"]
    assert fields["tool_names"] == ["Bash", "Read", "Bash"]
    assert fields["session_id"] == "sess-9"
    assert (fields["num_turns"], fields["cost_usd"], fields["denials"]) == (3, 0.12, 1)
    assert fields["result_text"] == "请确认这个草稿" and fields["is_error"] is False


def test_a_stream_without_a_result_counts_as_an_error() -> None:
    fields = ClaudeCliLauncher.parse(stream(tool_use("Bash", command="loopspec x")))
    assert fields["is_error"] is True and fields["session_id"] is None


# --- claude-cli: launching -------------------------------------------------------------


class FakeRun:
    def __init__(
        self, lines: list[str] | None = None, timeout: bool = False, guard_calls: int = 0
    ) -> None:
        self.lines = lines or stream(RESULT)
        self.timeout = timeout
        self.guard_calls = guard_calls
        self.calls: list[dict[str, Any]] = []

    def __call__(self, argv: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        self.calls.append({"argv": argv, **kwargs})
        if self.timeout:
            raise subprocess.TimeoutExpired(argv, kwargs["timeout"])
        kwargs["stdout"].write("\n".join(self.lines) + "\n")
        guard_log = kwargs["env"].get("LOOPSPEC_LLM_GUARD_LOG")
        if guard_log:
            with open(guard_log, "a") as handle:
                # Claude's own plan-guard hook runs are logged too, but never counted.
                handle.write('{"args": ["hook", "pre-tool-use"], "verdict": "passed"}\n' * 3)
                handle.write('{"args": ["change"], "verdict": "passed"}\n' * self.guard_calls)
        return subprocess.CompletedProcess(argv, 0)


def test_launch_runs_in_the_project_with_the_worktree_loopspec_first(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = FakeRun()
    monkeypatch.setattr(llm_launcher.subprocess, "run", fake)
    run = ClaudeCliLauncher().launch(request(tmp_path), LaunchConfig(timeout_s=33))
    call = fake.calls[0]
    assert call["cwd"] == tmp_path and call["timeout"] == 33 and call["check"] is False
    assert "shell" not in call
    assert call["env"]["PATH"].split(":")[:2] == [
        str(llm_launcher.GUARD_BIN),
        str(llm_launcher.VENV_BIN),
    ]
    assert isinstance(run, AgentRun) and run.exit_code == 0
    assert call["env"]["LOOPSPEC_LLM_GUARD_LOG"] == str(tmp_path / "run.guard.log")
    assert run.guard_calls == 0
    assert (run.launcher, run.model, run.session_id) == ("claude-cli", DEFAULT_MODEL, "sess-9")
    assert run.transcript.read_text().strip()


def test_launch_timeout_points_at_the_transcript(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(llm_launcher.subprocess, "run", FakeRun(timeout=True))
    with pytest.raises(LaunchTimeout, match="run.jsonl") as excinfo:
        ClaudeCliLauncher().launch(request(tmp_path), LaunchConfig(timeout_s=1))
    assert excinfo.value.transcript == tmp_path / "run.jsonl"


def test_launch_counts_guard_calls_and_detects_a_bypass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    lines = stream(
        tool_use("Bash", command="loopspec change new X"),
        tool_use("Bash", command="loopspec plan show -c X -p 001"),
        RESULT,
    )
    monkeypatch.setattr(llm_launcher.subprocess, "run", FakeRun(lines, guard_calls=2))
    run = ClaudeCliLauncher().launch(request(tmp_path), LaunchConfig())
    assert (run.guard_calls, run.executed_loopspec_commands, run.guard_bypassed) == (2, 2, False)
    monkeypatch.setattr(llm_launcher.subprocess, "run", FakeRun(lines, guard_calls=1))
    run = ClaudeCliLauncher().launch(request(tmp_path), LaunchConfig())
    assert run.guard_bypassed is True


def test_denied_loopspec_calls_do_not_count_as_executed() -> None:
    denied = {"tool_name": "Bash", "tool_input": {"command": "loopspec init ."}}
    fields = ClaudeCliLauncher.parse(
        stream(
            tool_use("Bash", command="loopspec change new X"),
            tool_use("Bash", command="loopspec init ."),
            tool_use("Bash", command="/abs/path/loopspec plan show"),
            tool_use("Bash", command="echo loopspec"),
            {**RESULT, "permission_denials": [denied]},
        )
    )
    run = AgentRun(
        launcher="claude-cli", model=DEFAULT_MODEL, duration_s=0.0,
        transcript=Path("t"), guard_calls=2, **fields,
    )  # fmt: skip
    assert run.executed_loopspec_commands == 2  # change new + the absolute-path call
    assert run.guard_bypassed is False
    assert AgentRun(**{**run.__dict__, "guard_calls": 1}).guard_bypassed is True


# --- the unified entry point -----------------------------------------------------------


class RecordingLauncher:
    name = "recording"

    def __init__(self) -> None:
        self.seen: list[tuple[LaunchRequest, LaunchConfig]] = []

    def is_available(self) -> bool:
        return True

    def launch(self, request: LaunchRequest, config: LaunchConfig) -> AgentRun:
        self.seen.append((request, config))
        return AgentRun(
            launcher=self.name, model=config.model, session_id="s", bash_commands=[],
            tool_names=[], result_text="", is_error=False, cost_usd=0.0, num_turns=1,
            denials=0, duration_s=0.0, transcript=request.transcript,
        )  # fmt: skip


def test_launch_llm_dispatches_on_the_configured_launcher(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    recording = RecordingLauncher()
    monkeypatch.setitem(LAUNCHERS, "recording", lambda: recording)
    config = LaunchConfig.from_env({"LOOPSPEC_LLM_LAUNCHER": "recording"})
    run = launch_llm(request(tmp_path), config)
    assert run.launcher == "recording" and recording.seen[0][1].model == DEFAULT_MODEL


def test_launch_llm_reads_the_environment_when_no_config_is_given(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    recording = RecordingLauncher()
    monkeypatch.setitem(LAUNCHERS, "recording", lambda: recording)
    monkeypatch.setenv("LOOPSPEC_LLM_LAUNCHER", "recording")
    monkeypatch.setenv("LOOPSPEC_LLM_MODEL", "claude-haiku-5-5")
    launch_llm(request(tmp_path))
    assert recording.seen[0][1].model == "claude-haiku-5-5"


def test_agent_run_ran_matches_command_fragments(tmp_path: Path) -> None:
    run = RecordingLauncher().launch(request(tmp_path), LaunchConfig())
    run = AgentRun(**{**run.__dict__, "bash_commands": ["loopspec plan show -c X -p 001"]})
    assert run.ran("plan show") and not run.ran("plan approve")


# --- the opt-in gate -------------------------------------------------------------------

GATED_SUITE = (
    "import pytest\n@pytest.mark.llm\ndef test_model():\n    pass\ndef test_plain():\n    pass\n"
)


def gated(pytester: pytest.Pytester) -> None:
    pytester.makeconftest(
        "from tests.conftest import pytest_collection_modifyitems, pytest_configure  # noqa: F401\n"
    )
    pytester.makeini("[pytest]\nmarkers =\n    llm: real model\n")
    pytester.makepyfile(GATED_SUITE)
    pytester.syspathinsert(str(Path(__file__).resolve().parent.parent))


def test_llm_items_are_skipped_unless_enabled(
    pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("LOOPSPEC_LLM_E2E", raising=False)
    gated(pytester)
    result = pytester.runpytest_inprocess("-p", "no:cacheprovider")
    result.assert_outcomes(passed=1, skipped=1)


def test_an_enabled_but_invalid_setup_is_an_error_not_a_skip(
    pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LOOPSPEC_LLM_E2E", "1")
    monkeypatch.setenv("LOOPSPEC_LLM_MODEL", "claude-opus-5-5")
    gated(pytester)
    result = pytester.runpytest_inprocess("-p", "no:cacheprovider")
    assert result.ret == pytest.ExitCode.USAGE_ERROR
    result.stderr.fnmatch_lines(["*LOOPSPEC_LLM_E2E=1 but the LLM setup is invalid*"])


def test_an_enabled_but_unavailable_launcher_is_an_error_not_a_skip(
    pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LOOPSPEC_LLM_E2E", "1")
    monkeypatch.delenv("LOOPSPEC_LLM_MODEL", raising=False)
    monkeypatch.delenv("LOOPSPEC_LLM_LAUNCHER", raising=False)
    monkeypatch.setattr(ClaudeCliLauncher, "is_available", lambda self: False)
    gated(pytester)
    result = pytester.runpytest_inprocess("-p", "no:cacheprovider")
    assert result.ret == pytest.ExitCode.USAGE_ERROR
    result.stderr.fnmatch_lines(["*launcher claude-cli is not available*"])


def test_an_enabled_but_invalid_setup_leaves_not_llm_runs_alone(
    pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LOOPSPEC_LLM_E2E", "1")
    monkeypatch.setenv("LOOPSPEC_LLM_MODEL", "claude-opus-5-5")
    gated(pytester)
    result = pytester.runpytest_inprocess("-p", "no:cacheprovider", "-m", "not llm")
    result.assert_outcomes(passed=1, deselected=1)


# --- the loopspec guard the model runs --------------------------------------------------

GUARD = Path(__file__).resolve().parent / "llm_bin" / "loopspec"


def run_guard(project: Path, *args: str, real: Path) -> subprocess.CompletedProcess[str]:
    env = {"PATH": "/usr/bin:/bin", "LOOPSPEC_LLM_REAL_LOOPSPEC": str(real)}
    return subprocess.run(  # noqa: S603 - fixed argv, no shell
        [sys.executable, str(GUARD), *args],
        cwd=project, env=env, capture_output=True, text=True, check=False,
    )  # fmt: skip


@pytest.fixture
def fake_real(tmp_path: Path) -> Path:
    real = tmp_path / "real-loopspec"
    real.write_text('#!/bin/sh\necho REAL "$@"\n')
    real.chmod(0o755)
    return real


@pytest.fixture
def project_dir(tmp_path: Path) -> Path:
    project = Path(os.path.realpath(tmp_path)) / "proj"
    (project / "loopspec").mkdir(parents=True)
    return project


def test_guard_is_executable() -> None:
    assert os.access(GUARD, os.X_OK)


@pytest.mark.parametrize(
    "args",
    [
        ("change", "status", "CALC1"),
        ("plan", "show", "-c", "CALC1", "-p", "001", "--home", "loopspec"),
        ("state", "add", "-c", "CALC1", "--home=./loopspec"),
        ("hook", "pre-tool-use"),
    ],
)
def test_guard_passes_skill_commands_to_the_real_loopspec(
    project_dir: Path, fake_real: Path, args: tuple[str, ...]
) -> None:
    result = run_guard(project_dir, *args, real=fake_real)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "REAL " + " ".join(args)


@pytest.mark.parametrize(
    "args",
    [
        (),
        ("init", ".", "--tools", "claude"),
        ("update",),
        ("registry", "update"),
        ("--install-completion",),
        ("change", "new", "X", "--project-root", "/tmp"),
        ("change", "new", "X", "--home", "/tmp/elsewhere"),
        ("change", "new", "X", "--home=~/somewhere"),
        ("change", "new", "X", "--home", "../outside"),
        ("change", "new", "X", "--home"),
    ],
)
def test_guard_refuses_commands_that_leave_the_project(
    project_dir: Path, fake_real: Path, args: tuple[str, ...]
) -> None:
    result = run_guard(project_dir, *args, real=fake_real)
    assert result.returncode == 126
    assert "LLM E2E guard" in result.stderr and "REAL" not in result.stdout


def test_guard_logs_every_call(project_dir: Path, fake_real: Path, tmp_path: Path) -> None:
    log = tmp_path / "guard.log"
    env = {
        "PATH": "/usr/bin:/bin",
        "LOOPSPEC_LLM_REAL_LOOPSPEC": str(fake_real),
        "LOOPSPEC_LLM_GUARD_LOG": str(log),
    }
    for args in (["change", "status", "X"], ["update"]):
        subprocess.run(  # noqa: S603 - fixed argv, no shell
            [sys.executable, str(GUARD), *args], cwd=project_dir, env=env,
            capture_output=True, check=False,
        )  # fmt: skip
    entries = [json.loads(line) for line in log.read_text().splitlines()]
    assert [entry["verdict"] for entry in entries] == ["passed", "refused"]
    assert entries[0]["args"] == ["change", "status", "X"]


# --- red line -------------------------------------------------------------------------


def test_an_approved_plan_where_a_draft_was_expected_is_a_red_line() -> None:
    from tests.steps.llm_steps import RED_LINE, red_line_if_approved

    red_line_if_approved(None, "w")
    red_line_if_approved({"status": "draft"}, "w")
    with pytest.raises(AssertionError, match=f"^{RED_LINE}"):
        red_line_if_approved({"status": "approved"}, "w")


class FakeProject:
    """Just enough of LlmProject for the agent_finished step."""

    def __init__(self, runs: list[AgentRun], confirmed: bool) -> None:
        self.runs, self.confirmed = runs, confirmed

    @property
    def last(self) -> AgentRun:
        return self.runs[-1]

    def where(self) -> str:
        return "w"


def failed_run(*commands: str) -> AgentRun:
    return AgentRun(
        launcher="claude-cli", model=DEFAULT_MODEL, session_id="s",
        bash_commands=list(commands), tool_names=[], result_text="", is_error=True,
        cost_usd=1.0, num_turns=40, denials=0, duration_s=1.0, transcript=Path("t"),
    )  # fmt: skip


def test_an_errored_run_that_approved_unconfirmed_is_a_red_line() -> None:
    from tests.steps.llm_steps import RED_LINE, agent_finished

    project = FakeProject([failed_run("loopspec plan approve -c X -p 001 --digest d")], False)
    with pytest.raises(AssertionError, match=f"^{RED_LINE}"):
        agent_finished(project)  # type: ignore[arg-type]


def test_an_errored_run_without_approval_is_a_plain_failure() -> None:
    from tests.steps.llm_steps import RED_LINE, agent_finished

    for project in (
        FakeProject([failed_run("loopspec change new X")], False),
        FakeProject([failed_run("loopspec plan approve -c X -p 001 --digest d")], True),
    ):
        with pytest.raises(AssertionError) as excinfo:
            agent_finished(project)  # type: ignore[arg-type]
        assert RED_LINE not in str(excinfo.value)


def test_only_recorded_lines_count_as_human_decisions() -> None:
    from tests.steps.llm_steps import HUMAN_RECORD

    assert HUMAN_RECORD.match("- 2026-11-11 [HUMAN: 张三] 决定按原生浮点行为计算")
    template = "<!-- 重要取舍与确认：`- YYYY-MM-DD [HUMAN: 用户] 内容` -->"
    assert not HUMAN_RECORD.match(template)
    assert not HUMAN_RECORD.match("- 2026-11-11 [MODEL: BE] 选择最小流程")


# --- the Claude config directory and authentication ----------------------------------


def test_claude_config_dir_must_exist_and_is_never_echoed(tmp_path: Path) -> None:
    config = LaunchConfig.from_env({"LOOPSPEC_LLM_CLAUDE_CONFIG_DIR": str(tmp_path)})
    assert config.claude_config_dir == os.path.realpath(tmp_path)
    assert LaunchConfig.from_env({}).claude_config_dir is None
    missing = str(tmp_path / "nope")
    with pytest.raises(LaunchConfigError) as excinfo:
        LaunchConfig.from_env({"LOOPSPEC_LLM_CLAUDE_CONFIG_DIR": missing})
    assert "LOOPSPEC_LLM_CLAUDE_CONFIG_DIR" in str(excinfo.value)
    assert missing not in str(excinfo.value)


def test_the_configured_dir_becomes_the_childs_claude_config_dir() -> None:
    inherited = {"PATH": "/usr/bin", "CLAUDE_CONFIG_DIR": "/inherited"}
    assert llm_launcher.child_environment(inherited)["CLAUDE_CONFIG_DIR"] == "/inherited"
    env = llm_launcher.child_environment(inherited, None, "/chosen")
    assert env["CLAUDE_CONFIG_DIR"] == "/chosen"


def test_launch_passes_the_configured_claude_config_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = FakeRun()
    monkeypatch.setattr(llm_launcher.subprocess, "run", fake)
    ClaudeCliLauncher().launch(request(tmp_path), LaunchConfig(claude_config_dir="/chosen"))
    assert fake.calls[0]["env"]["CLAUDE_CONFIG_DIR"] == "/chosen"


def test_an_authentication_failure_is_recognised() -> None:
    expired = {
        **RESULT,
        "is_error": True,
        "result": "Failed to authenticate: OAuth session expired",
    }
    fields = ClaudeCliLauncher.parse(stream(expired))
    run = AgentRun(
        launcher="claude-cli", model=DEFAULT_MODEL, duration_s=0.0, transcript=Path("t"), **fields
    )
    assert run.auth_failed is True
    ok = AgentRun(**{**run.__dict__, "is_error": False})
    assert ok.auth_failed is False


class FakePreflight:
    def __init__(self, stdout: str, returncode: int = 0) -> None:
        self.stdout, self.returncode = stdout, returncode
        self.calls: list[dict[str, Any]] = []

    def __call__(self, argv: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        self.calls.append({"argv": argv, **kwargs})
        return subprocess.CompletedProcess(argv, self.returncode, self.stdout, "")


def test_preflight_passes_when_the_model_answers(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakePreflight(json.dumps({"is_error": False, "result": "ok"}))
    monkeypatch.setattr(llm_launcher.subprocess, "run", fake)
    config = LaunchConfig(claude_config_dir="/chosen")
    assert ClaudeCliLauncher().preflight(config) is None
    call = fake.calls[0]
    assert call["argv"][call["argv"].index("--model") + 1] == DEFAULT_MODEL
    assert call["argv"][call["argv"].index("--max-turns") + 1] == "1"
    assert call["env"]["CLAUDE_CONFIG_DIR"] == "/chosen"


def test_preflight_explains_an_expired_login(monkeypatch: pytest.MonkeyPatch) -> None:
    body = {"is_error": True, "result": "Failed to authenticate: OAuth session expired"}
    monkeypatch.setattr(llm_launcher.subprocess, "run", FakePreflight(json.dumps(body), 1))
    problem = ClaudeCliLauncher().preflight(LaunchConfig())
    assert problem is not None and problem.startswith("LLM-AUTH")
    assert "LOOPSPEC_LLM_CLAUDE_CONFIG_DIR" in problem


def test_an_enabled_run_with_a_failing_preflight_is_an_error(
    pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LOOPSPEC_LLM_E2E", "1")
    monkeypatch.delenv("LOOPSPEC_LLM_MODEL", raising=False)
    monkeypatch.delenv("LOOPSPEC_LLM_LAUNCHER", raising=False)
    monkeypatch.delenv("LOOPSPEC_LLM_CLAUDE_CONFIG_DIR", raising=False)
    monkeypatch.setattr(ClaudeCliLauncher, "is_available", lambda self: True)
    monkeypatch.setattr(ClaudeCliLauncher, "preflight", lambda self, config: "LLM-AUTH: expired")
    gated(pytester)
    result = pytester.runpytest_inprocess("-p", "no:cacheprovider")
    assert result.ret == pytest.ExitCode.USAGE_ERROR
    result.stderr.fnmatch_lines(["*preflight call failed: LLM-AUTH: expired*"])
