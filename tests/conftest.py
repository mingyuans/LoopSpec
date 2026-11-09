"""Shared fixtures for the BDD scenarios, split by responsibility (no catch-all world object)."""

from __future__ import annotations

import fcntl
import os
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from tests.workflow_helpers import CHANGE, invoke, project


@dataclass
class CliOutcome:
    """What a scenario needs from one CLI call: the exit code and the parsed JSON."""

    code: int
    data: dict


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
def change_lock(home: Path) -> Iterator[ChangeLock]:
    lock = ChangeLock(home / "changes" / CHANGE / "plans" / ".write.lock")
    yield lock
    lock.release()
