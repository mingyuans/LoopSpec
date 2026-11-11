"""The one way LLM end-to-end scenarios start a model: `launch_llm(request, config)`.

Scenarios and steps never build a command line or pick a model themselves. Everything
that may change later -- how the model is started (`launcher`), which model, its budget,
turn and time limits -- lives in `LaunchConfig`, read from the environment by NAME only.
Switching to another way of starting an LLM means registering a new `Launcher` in
`LAUNCHERS` and selecting it with LOOPSPEC_LLM_LAUNCHER; no scenario code changes.

Values are validated but never echoed: an error names the variable, not its content.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol, TypeVar

REPO_ROOT = Path(__file__).resolve().parent.parent
#: The worktree's own loopspec, so the code under test is exercised ...
VENV_BIN = REPO_ROOT / ".venv" / "bin"
#: ... reached only through the guard in tests/llm_bin/loopspec, which is first on PATH.
GUARD_BIN = REPO_ROOT / "tests" / "llm_bin"
ENV_REAL_LOOPSPEC = "LOOPSPEC_LLM_REAL_LOOPSPEC"
ENV_GUARD_LOG = "LOOPSPEC_LLM_GUARD_LOG"
#: The loopspec subcommands the skills use; the guard and the Bash rules allow only these.
LOOPSPEC_SUBCOMMANDS = ("change", "plan", "node", "gate", "state", "memory", "fragment", "profile")

ENV_LAUNCHER = "LOOPSPEC_LLM_LAUNCHER"
ENV_MODEL = "LOOPSPEC_LLM_MODEL"
ENV_BUDGET = "LOOPSPEC_LLM_BUDGET_USD"
ENV_MAX_TURNS = "LOOPSPEC_LLM_MAX_TURNS"
ENV_TIMEOUT = "LOOPSPEC_LLM_TIMEOUT"
#: Which Claude configuration (login, credentials) the model uses. Passed to the child as
#: CLAUDE_CONFIG_DIR; unset means the inherited CLAUDE_CONFIG_DIR (or Claude's default).
ENV_CLAUDE_CONFIG_DIR = "LOOPSPEC_LLM_CLAUDE_CONFIG_DIR"
#: Marks a failure that is the machine's login, not the scenario; never retried.
LLM_AUTH = "LLM-AUTH"
_AUTH_FAILURES = (
    "failed to authenticate", "oauth", "invalid api key", "please run /login", "not logged in",
)  # fmt: skip

#: A capable but not the strongest model; always passed explicitly.
DEFAULT_MODEL = "claude-sonnet-5-5"
#: Only Sonnet/Haiku model ids are accepted (ASCII, no aliases), so Opus is never selected.
ALLOWED_MODEL = re.compile(r"claude-(?:sonnet|haiku)-[0-9][0-9a-z.-]*", re.ASCII)

#: Environment variable NAMES passed to the model process; values are never inspected.
#: Everything else (cloud keys, tokens of other tools) is withheld from the model's shell.
ENV_PASS_NAMES = frozenset(
    {
        "HOME", "USER", "LOGNAME", "SHELL", "LANG", "TERM", "TMPDIR", "PATH",
        # Network plumbing, not credentials: needed behind a proxy or a corporate CA.
        "HTTPS_PROXY", "HTTP_PROXY", "NO_PROXY", "https_proxy", "http_proxy", "no_proxy",
        "NODE_EXTRA_CA_CERTS", "SSL_CERT_FILE", "SSL_CERT_DIR",
    }
)  # fmt: skip
ENV_PASS_PREFIXES = ("LC_", "CLAUDE_", "ANTHROPIC_")


class LaunchConfigError(ValueError):
    """A launch setting is invalid; the message names the variable, never its value."""


class LaunchTimeout(RuntimeError):
    """The model did not finish in time; the transcript path is in the message."""

    def __init__(self, message: str, transcript: Path, duration_s: float) -> None:
        super().__init__(message)
        self.transcript = transcript
        self.duration_s = duration_s


@dataclass(frozen=True)
class LaunchConfig:
    launcher: str = "claude-cli"
    model: str = DEFAULT_MODEL
    max_budget_usd: float = 1.0
    max_turns: int = 40
    timeout_s: int = 600
    claude_config_dir: str | None = None

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> LaunchConfig:
        env = os.environ if environ is None else environ
        defaults = cls()
        launcher = env.get(ENV_LAUNCHER) or defaults.launcher
        if launcher not in LAUNCHERS:
            raise LaunchConfigError(f"{ENV_LAUNCHER} names no registered launcher")
        model = env.get(ENV_MODEL) or defaults.model
        if not ALLOWED_MODEL.fullmatch(model):
            # An allow-list, not a deny-list: aliases such as "default" may resolve to Opus.
            raise LaunchConfigError(
                f"{ENV_MODEL} must name a Sonnet or Haiku model (claude-sonnet-*/claude-haiku-*)"
            )
        return cls(
            launcher=launcher,
            model=model,
            max_budget_usd=_positive(env, ENV_BUDGET, float, defaults.max_budget_usd),
            max_turns=_positive(env, ENV_MAX_TURNS, int, defaults.max_turns),
            timeout_s=_positive(env, ENV_TIMEOUT, int, defaults.timeout_s),
            claude_config_dir=_existing_dir(env, ENV_CLAUDE_CONFIG_DIR),
        )


def _existing_dir(env: Mapping[str, str], name: str) -> str | None:
    raw = env.get(name)
    if not raw:
        return None
    path = os.path.realpath(os.path.expanduser(raw))
    if not os.path.isdir(path):
        raise LaunchConfigError(f"{name} must name an existing directory")
    return path


Number = TypeVar("Number", int, float)


def _positive(env: Mapping[str, str], name: str, kind: type[Number], default: Number) -> Number:
    raw = env.get(name)
    if not raw:
        return default
    try:
        value = kind(raw)
    except ValueError:
        raise LaunchConfigError(f"{name} must be a positive {kind.__name__}") from None
    if value <= 0:
        raise LaunchConfigError(f"{name} must be a positive {kind.__name__}")
    return value


@dataclass(frozen=True)
class LaunchRequest:
    project: Path
    prompt: str
    transcript: Path
    resume: str | None = None


@dataclass(frozen=True)
class AgentRun:
    """What every launcher reports, whatever the underlying tool."""

    launcher: str
    model: str
    session_id: str | None
    bash_commands: list[str]
    tool_names: list[str]
    result_text: str
    is_error: bool
    cost_usd: float | None
    num_turns: int | None
    denials: int
    duration_s: float
    transcript: Path
    exit_code: int | None = None
    #: How many times the loopspec guard was called; None when the launcher has no guard.
    guard_calls: int | None = None
    raw_result: dict[str, Any] = field(default_factory=dict, repr=False)

    def ran(self, fragment: str) -> bool:
        """Whether any shell command the model ran contains `fragment`."""
        return any(fragment in command for command in self.bash_commands)

    @property
    def executed_loopspec_commands(self) -> int:
        """Bash calls that invoked loopspec and were not denied by the permission rules."""
        denied = [
            str((denial.get("tool_input") or {}).get("command", ""))
            for denial in self.raw_result.get("permission_denials") or []
            if isinstance(denial, dict)
        ]
        issued = [command for command in self.bash_commands if _invokes_loopspec(command)]
        for command in denied:
            if command in issued:
                issued.remove(command)
        return len(issued)

    @property
    def auth_failed(self) -> bool:
        """The model never ran because the CLI could not authenticate."""
        text = self.result_text.lower()
        return self.is_error and any(marker in text for marker in _AUTH_FAILURES)

    @property
    def guard_bypassed(self) -> bool:
        """True when some executed loopspec call never reached the guard."""
        return self.guard_calls is not None and self.guard_calls < self.executed_loopspec_commands


def _invokes_loopspec(command: str) -> bool:
    words = command.strip().split()
    return bool(words) and os.path.basename(words[0]) == "loopspec"


class Launcher(Protocol):
    name: str

    def is_available(self) -> bool: ...

    def preflight(self, config: LaunchConfig) -> str | None:
        """One minimal call before any scenario; returns a problem to report, or None."""
        ...

    def launch(self, request: LaunchRequest, config: LaunchConfig) -> AgentRun: ...


class ClaudeCliLauncher:
    """`claude -p`, isolated from the user's own settings and MCP servers."""

    name = "claude-cli"
    executable = "claude"
    #: Bash runs the skills' loopspec subcommands only (and `loopspec` itself is the guard
    #: in tests/llm_bin, which refuses options that leave the project); file tools are
    #: scoped to the cwd (the throwaway project) and the home directory is denied outright,
    #: so the model cannot reach the user's files or credentials. `--setting-sources
    #: project` drops the user's own deny rules, which is why these limits live here.
    allowed_tools = (
        *(f"Bash(loopspec {command}:*)" for command in LOOPSPEC_SUBCOMMANDS),
        "Read(./**)", "Write(./**)", "Edit(./**)", "Glob(./**)", "Grep(./**)",
    )  # fmt: skip
    disallowed_tools = ("Read(~/**)", "Write(~/**)", "Edit(~/**)", "Glob(~/**)", "Grep(~/**)")
    #: Tells the model about the harness, not about the skill: without it, a model that
    #: chains `mkdir && cat > … && loopspec …` is denied and may give up half way.
    harness_prompt = (
        "You are running inside an automated end-to-end test, in a throwaway project that is"
        " your working directory. Bash may only run a single `loopspec ...` command per call:"
        " no `cd`, no `&&`, `;`, pipes, redirects or heredocs, and no other programs. Create"
        " and edit files with the Write and Edit tools, and read them with Read, Glob and"
        " Grep, using paths inside the working directory."
    )

    def is_available(self) -> bool:
        return shutil.which(self.executable) is not None

    def preflight(self, config: LaunchConfig) -> str | None:
        """A single cheap turn in an empty directory: is the login usable right now?

        Run once, serially, before the parallel workers start, which also refreshes an
        expiring OAuth token in one process instead of racing it in several.
        """
        import tempfile

        with tempfile.TemporaryDirectory(prefix="llm-preflight-") as workdir:
            argv = [
                self.executable, "-p", "Reply with the single word: ok",
                "--model", config.model, "--setting-sources", "project",
                "--strict-mcp-config", "--max-turns", "1", "--output-format", "json",
            ]  # fmt: skip
            try:
                completed = subprocess.run(  # noqa: S603 - argv list, no shell
                    argv, cwd=os.path.realpath(workdir), capture_output=True, text=True,
                    env=child_environment(os.environ, None, config.claude_config_dir),
                    timeout=120, check=False,
                )  # fmt: skip
            except subprocess.TimeoutExpired:
                return f"{self.name}: the preflight call did not finish within 120s"
        try:
            result = json.loads(completed.stdout or "{}")
        except json.JSONDecodeError:
            result = {}
        text = str(result.get("result") or completed.stderr or "").lower()
        if result.get("is_error", completed.returncode != 0):
            if any(marker in text for marker in _AUTH_FAILURES):
                return (
                    f"{LLM_AUTH}: claude could not authenticate with the Claude config it was"
                    f" given. Set {ENV_CLAUDE_CONFIG_DIR} to the config directory you log in"
                    " with (or export CLAUDE_CONFIG_DIR), or run `claude` and /login again."
                )
            return f"{self.name}: the preflight call failed (exit {completed.returncode})"
        return None

    def argv(self, request: LaunchRequest, config: LaunchConfig) -> list[str]:
        argv = [
            self.executable, "-p", request.prompt,
            "--model", config.model,
            "--setting-sources", "project",
            "--strict-mcp-config",
            "--permission-mode", "dontAsk",
            "--max-turns", str(config.max_turns),
            "--max-budget-usd", str(config.max_budget_usd),
            "--output-format", "stream-json", "--verbose",
            "--append-system-prompt", self.harness_prompt,
            "--disallowedTools", *self.disallowed_tools,
            "--allowedTools", *self.allowed_tools,
        ]  # fmt: skip
        if request.resume:
            argv += ["--resume", request.resume]
        return argv

    @staticmethod
    def parse(lines: Iterable[str]) -> dict[str, Any]:
        """stream-json events -> AgentRun fields; malformed lines are skipped."""
        bash: list[str] = []
        tools: list[str] = []
        result: dict[str, Any] = {}
        for line in lines:
            try:
                event = json.loads(line)
            except (json.JSONDecodeError, TypeError):
                continue
            if not isinstance(event, dict):
                continue
            if event.get("type") == "assistant":
                for block in (event.get("message") or {}).get("content") or []:
                    if isinstance(block, dict) and block.get("type") == "tool_use":
                        tools.append(str(block.get("name")))
                        if block.get("name") == "Bash":
                            bash.append(str((block.get("input") or {}).get("command", "")))
            elif event.get("type") == "result":
                result = event
        return {
            "session_id": result.get("session_id"),
            "bash_commands": bash,
            "tool_names": tools,
            "result_text": str(result.get("result") or ""),
            "is_error": bool(result.get("is_error", not result)),
            "cost_usd": result.get("total_cost_usd"),
            "num_turns": result.get("num_turns"),
            "denials": len(result.get("permission_denials") or []),
            "raw_result": result,
        }

    def launch(self, request: LaunchRequest, config: LaunchConfig) -> AgentRun:
        request.transcript.parent.mkdir(parents=True, exist_ok=True)
        guard_log = request.transcript.with_suffix(".guard.log")
        guard_log.write_text("")
        env = child_environment(os.environ, guard_log, config.claude_config_dir)
        stderr_path = request.transcript.with_suffix(".stderr.txt")
        started = time.monotonic()
        with request.transcript.open("w") as out, stderr_path.open("w") as err:
            try:
                completed = subprocess.run(  # noqa: S603 - argv list, no shell
                    self.argv(request, config), cwd=request.project, env=env,
                    stdout=out, stderr=err, timeout=config.timeout_s, check=False,
                )  # fmt: skip
            except subprocess.TimeoutExpired:
                raise LaunchTimeout(
                    f"{self.name} did not finish within {config.timeout_s}s;"
                    f" transcript: {request.transcript}",
                    request.transcript,
                    time.monotonic() - started,
                ) from None
        duration = time.monotonic() - started
        fields = self.parse(request.transcript.read_text().splitlines())
        return AgentRun(
            launcher=self.name, model=config.model, duration_s=duration,
            transcript=request.transcript, exit_code=completed.returncode,
            guard_calls=model_guard_calls(guard_log), **fields,
        )  # fmt: skip


def child_environment(
    environ: Mapping[str, str],
    guard_log: Path | None = None,
    claude_config_dir: str | None = None,
) -> dict[str, str]:
    """The model's environment: allow-listed variable names only; the guarded loopspec first."""
    env = {
        name: value
        for name, value in environ.items()
        if name in ENV_PASS_NAMES or name.startswith(ENV_PASS_PREFIXES)
    }
    env["PATH"] = os.pathsep.join([str(GUARD_BIN), str(VENV_BIN), env.get("PATH", "")])
    env[ENV_REAL_LOOPSPEC] = str(VENV_BIN / "loopspec")
    if guard_log is not None:
        env[ENV_GUARD_LOG] = str(guard_log)
    if claude_config_dir is not None:
        env["CLAUDE_CONFIG_DIR"] = claude_config_dir
    return env


def model_guard_calls(guard_log: Path) -> int:
    """Guard calls made by the model; Claude's own plan-guard hook runs are not counted."""
    calls = 0
    for line in guard_log.read_text().splitlines():
        try:
            args = json.loads(line).get("args") or []
        except (json.JSONDecodeError, AttributeError):
            continue
        if args[:1] != ["hook"]:
            calls += 1
    return calls


#: Every way of starting an LLM, by the name LOOPSPEC_LLM_LAUNCHER selects.
LAUNCHERS: dict[str, Callable[[], Launcher]] = {ClaudeCliLauncher.name: ClaudeCliLauncher}


def get_launcher(config: LaunchConfig) -> Launcher:
    try:
        return LAUNCHERS[config.launcher]()
    except KeyError:
        raise LaunchConfigError(f"{ENV_LAUNCHER} names no registered launcher") from None


def launch_llm(request: LaunchRequest, config: LaunchConfig | None = None) -> AgentRun:
    """The single entry point: start the configured model on `request` and report the run."""
    config = config or LaunchConfig.from_env()
    return get_launcher(config).launch(request, config)
