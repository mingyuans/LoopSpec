"""Shared fixtures for the BDD scenarios, split by responsibility (no catch-all world object).

Step definitions live in `tests/steps`; listing them here registers them for every feature.
"""

from __future__ import annotations

import fcntl
import json
import os
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import pytest
from typer.testing import CliRunner

from loopspec.cli import app
from tests.workflow_helpers import CHANGE, invoke, project

#: Real-model scenarios run only when this is exactly "1" and the launcher is available.
LLM_ENABLE_ENV = "LOOPSPEC_LLM_E2E"
LLM_RUNS_DIR_ENV = "LOOPSPEC_LLM_RUNS_DIR"

pytest_plugins = [
    "tests.steps.common",
    "tests.steps.catalog_steps",
    "tests.steps.change_steps",
    "tests.steps.init_steps",
    "tests.steps.memory_steps",
    "tests.steps.node_gate_steps",
    "tests.steps.plan_guard_steps",
    "tests.steps.plan_revision_steps",
    "tests.steps.plan_steps",
    "tests.steps.registry_steps",
    "tests.steps.state_add_steps",
    "tests.steps.update_steps",
    "tests.steps.version_steps",
    "tests.steps.llm_steps",
    "pytester",
]


def _selects_llm(config: pytest.Config) -> bool:
    """Whether the -m expression would keep an item marked `llm` (no -m keeps everything)."""
    markexpr = config.option.markexpr
    if not markexpr:
        return True
    try:  # pytest's own -m evaluator; private, so fall back to "selected" if it moves
        from _pytest.mark.expression import Expression

        return bool(Expression.compile(markexpr).evaluate(lambda name: name == "llm"))
    except (ImportError, AttributeError):
        return True


def pytest_configure(config: pytest.Config) -> None:
    """Validate an enabled LLM setup once, in the controller, before any worker starts.

    Enabled (LOOPSPEC_LLM_E2E=1) and selected by -m, a broken setup is a usage error -- an
    invalid model or launcher, or a launcher missing here -- rather than a silent skip.
    `-m "not llm"` (make test) is never affected, even with the variable exported.
    """
    if hasattr(config, "workerinput") or os.environ.get(LLM_ENABLE_ENV) != "1":
        return
    if not _selects_llm(config):
        return
    from tests.llm_launcher import REPO_ROOT, LaunchConfig, LaunchConfigError, get_launcher

    try:
        launcher = get_launcher(LaunchConfig.from_env())
    except LaunchConfigError as exc:
        raise pytest.UsageError(f"{LLM_ENABLE_ENV}=1 but the LLM setup is invalid: {exc}") from None
    if not launcher.is_available():
        raise pytest.UsageError(
            f"{LLM_ENABLE_ENV}=1 but launcher {launcher.name} is not available on this machine"
        )
    problem = launcher.preflight(LaunchConfig.from_env())
    if problem:
        raise pytest.UsageError(f"{LLM_ENABLE_ENV}=1 but the preflight call failed: {problem}")
    # One run-record directory for the whole run; xdist workers inherit the environment.
    if not os.environ.get(LLM_RUNS_DIR_ENV):
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        os.environ[LLM_RUNS_DIR_ENV] = str(REPO_ROOT / ".llm-e2e-runs" / stamp)


@pytest.hookimpl(trylast=True)
def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Skip `llm` scenarios unless explicitly enabled: they start a real, billed model."""
    if os.environ.get(LLM_ENABLE_ENV) == "1":
        return  # validated in pytest_configure
    skip = pytest.mark.skip(
        reason=f"set {LLM_ENABLE_ENV}=1 to run real-model scenarios (make test-llm)"
    )
    for item in items:
        if item.get_closest_marker("llm"):
            item.add_marker(skip)


@dataclass
class CliOutcome:
    """What a scenario needs from one CLI call: the exit code and the parsed JSON."""

    code: int
    data: dict
    output: str = ""


# A Plan whose QA Gate resets requirements and allows a single retry.
QA_FLOW_ONE_RETRY = [
    {"id": "requirements", "use": "requirements"},
    {
        "id": "qa",
        "use": "qa-testing",
        "requires": ["requirements"],
        "on_fail": {"reset": ["requirements"], "max_retries": 1},
    },
]


@dataclass
class LastCall:
    """The most recent CLI call of a scenario, so a retry can repeat it unchanged."""

    args: tuple[str, ...] = ()
    outcome: CliOutcome | None = None
    text: str = ""


@dataclass
class ChangeLock:
    """Holds the Change write lock the way another running command would."""

    path: Path
    _fd: int | None = field(default=None, init=False)

    def acquire(self) -> None:
        self._fd = os.open(self.path, os.O_RDWR | os.O_CREAT, 0o600)
        fcntl.flock(self._fd, fcntl.LOCK_EX)

    def release(self) -> None:
        if self._fd is not None:
            fcntl.flock(self._fd, fcntl.LOCK_UN)
            os.close(self._fd)
            self._fd = None


@pytest.fixture
def home(tmp_path: Path) -> Path:
    """An isolated workflow home inside its own Git repository."""
    return project(tmp_path)


@pytest.fixture
def run_cli(home: Path) -> Callable[..., CliOutcome]:
    """Call the real CLI in-process against `home`."""

    def run(*args: str) -> CliOutcome:
        code, data = invoke(home, *args)
        return CliOutcome(code, data)

    return run


@pytest.fixture
def run_app() -> Callable[..., CliOutcome]:
    """Call the real CLI in-process without `--home`, for init/version/update/hook."""

    def run(*args: str, input: str | None = None) -> CliOutcome:
        result = CliRunner().invoke(app, list(args), input=input)
        try:
            data = json.loads(result.stdout) if result.stdout.strip() else {}
        except json.JSONDecodeError:
            data = {}
        return CliOutcome(result.exit_code, data if isinstance(data, dict) else {}, result.stdout)

    return run


@pytest.fixture
def isolated_codex_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Codex keeps prompts in a global directory; point it inside the scenario's tmp_path."""
    codex_home = tmp_path / "codex-home"
    monkeypatch.setenv("CODEX_HOME", str(codex_home))
    return codex_home


@pytest.fixture
def last_call() -> LastCall:
    return LastCall()


@pytest.fixture
def file_fingerprints() -> dict[str, str]:
    """File path to content hash, taken just before a command runs."""
    return {}


@pytest.fixture
def rollback_log() -> list[int]:
    """Global sequence numbers returned by each `plan rollback` of the scenario."""
    return []


@pytest.fixture
def recorded_lines() -> list[str]:
    """Lines written by `state add` during the scenario, in order."""
    return []


@pytest.fixture
def home_snapshot() -> dict[str, bytes]:
    """Every file of the workflow home, taken just before a read-only command runs."""
    return {}


@pytest.fixture
def change_lock(home: Path) -> Iterator[ChangeLock]:
    lock = ChangeLock(home / "changes" / CHANGE / "plans" / ".write.lock")
    yield lock
    lock.release()
