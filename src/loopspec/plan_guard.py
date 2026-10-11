"""PreToolUse hook for Claude Code and Codex: LLM tools may not write an approved plan.yaml.

The engine itself writes plan.yaml (approve, revise, archive); this guard only sees the
tool calls an agent makes. Bash detection is a heuristic guardrail, not a security
boundary -- `read_plan`'s digest check stays the second line of defence.

Principle: deny what the guard can detect, and let everything else through, so it
never gets in the way of a normal tool call. Input too large to parse, analysis past
the time budget, nesting too deep, an unreadable plan.yaml or any other failure to
check all mean "not detected". Scans stay linear so that detection rarely runs out of
time in the first place.
"""

from __future__ import annotations

import glob
import json
import os
import re
import shlex
import signal
import stat
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from .workflow_yaml import parse_yaml

MAX_PLAN_BYTES = 2 * 1024 * 1024
MAX_HOOK_INPUT = 64 * 1024 * 1024
MAX_GLOB_MATCHES = 256
MAX_NESTING = 8
TIME_BUDGET_SECONDS = 10
_PLAN_DIR = re.compile(r"^[0-9]{3}$")
_PATH_STOP = set("'\"=(),;<>|&`") | {chr(code) for code in range(33)}
_GLOB_CHARS = "*?["
_APPROVED_LINE = re.compile(r"""^\+\s*status:\s*['"]?approved['"]?\s*$""")
_PATCH_HEADER = re.compile(r"^\*\*\* (Add File|Update File|Delete File|Move to): (.+)$")
_SEPARATORS = {";", ";;", "&&", "||", "|", "&", "|&", "(", ")"}
_REDIRECTS = {">", ">>", ">|", "&>", "&>>", "<>"}
_PREFIXES = {"env", "sudo", "command", "nohup", "time", "exec", "builtin"}
_READERS = {
    "cat", "head", "tail", "grep", "egrep", "fgrep", "rg", "wc", "diff", "cmp",
    "ls", "stat", "file", "sha256sum", "shasum", "md5", "md5sum", "yq", "jq", "bat", "echo",
    "loopspec", "git",
}  # fmt: skip
_GIT_READS = {"diff", "log", "show", "status", "blame"}
# Options that make an otherwise read-only program write a file or run a command.
# sed is not a reader at all: its `w` command writes files from inside the script.
_WRITING_OPTIONS = {"yq": ("--inplace", "-i"), "git": ("--output",), "rg": ("--pre",)}


# --- what is protected ----------------------------------------------------------------------


def _plan_shape(path: Path) -> tuple[Path, str] | None:
    """(change root, plan id) when path is <change>/plans/<NNN>/plan.yaml of a real Change."""
    plan_dir = path.parent
    if path.name != "plan.yaml" or not _PLAN_DIR.match(plan_dir.name):
        return None
    if plan_dir.parent.name != "plans":
        return None
    root = plan_dir.parent.parent
    if not (root / ".workflow.yaml").is_file():
        return None
    return root, plan_dir.name


def _status(text: str | bytes) -> str | None:
    """meta.status of a plan.yaml text; None when it cannot be read as one."""
    try:
        meta = parse_yaml(text).get("meta")
    except (ValueError, UnicodeError):
        return None
    status = meta.get("status") if isinstance(meta, dict) else None
    return status if isinstance(status, str) else None


class Undecidable(Exception):
    """The guard cannot check this call in a bounded way; the call is then let through."""


def _read_plan(path: Path) -> bytes | None:
    """The file's bytes; None if missing. Non-blocking, so a FIFO cannot stall the hook."""
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise Undecidable("unreadable plan.yaml") from exc
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_PLAN_BYTES:
            raise Undecidable("plan.yaml is not a regular file within the size limit")
        data = os.read(fd, MAX_PLAN_BYTES + 1)
    finally:
        os.close(fd)
    if len(data) > MAX_PLAN_BYTES:
        raise Undecidable("plan.yaml grew past the size limit")
    return data


def _current_status(path: Path) -> str | None:
    """The file's status; None when missing or when it cannot be read as a plan.yaml."""
    try:
        data = _read_plan(path)
    except Undecidable:
        return None
    return None if data is None else _status(data)


def _resolve(cwd: Path, value: str) -> Path:
    return Path(os.path.realpath(os.path.join(cwd, os.path.expanduser(value))))


class _Target:
    def __init__(self, path: Path, root: Path, plan: str) -> None:
        self.path, self.root, self.plan = path, root, plan

    @property
    def approved(self) -> bool:
        return _current_status(self.path) == "approved"

    def text(self) -> str | None:
        try:
            data = _read_plan(self.path)
            return None if data is None else data.decode("utf-8")
        except (Undecidable, UnicodeError):
            return None


def _target(cwd: Path, value: Any) -> _Target | None:
    if not isinstance(value, str) or not value or "\0" in value:
        return None
    path = _resolve(cwd, value)
    shape = _plan_shape(path)
    return _Target(path, *shape) if shape else None


# --- deny reasons ---------------------------------------------------------------------------


def _edit_reason(target: _Target) -> str:
    change, plan = target.root.name, target.plan
    return (
        f"LoopSpec: {target.path} belongs to approved Plan {plan} of change {change}; "
        "do not edit plan.yaml directly. "
        "To adjust the Plan, write a revision request, run "
        f"`loopspec plan validate -c {change} -f <request>`, show the human the digest, and "
        "after they confirm run "
        f"`loopspec plan approve -c {change} -p {plan} -f <request> --digest <digest>`. "
        "If the flow no longer fits, get the human's consent, run "
        f"`loopspec plan archive -c {change} -p {plan} --note <reason>`, "
        "then plan again with `loopspec plan create`."
    )


def _forge_reason(target: _Target) -> str:
    change, plan = target.root.name, target.plan
    return (
        f"LoopSpec: writing an approved plan.yaml by hand ({target.path}) is not allowed; "
        "only loopspec plan approve can approve a Plan. Show the draft with "
        f"`loopspec plan show -c {change} -p {plan}` and, after the human confirms, run "
        f"`loopspec plan approve -c {change} -p {plan} --digest <digest>` "
        "(use `plan approve -f` for a revision, or `plan archive` to start over)."
    )


# --- edit tools -----------------------------------------------------------------------------


def _replace(text: str, old: Any, new: Any, every: Any) -> str | None:
    if not isinstance(old, str) or not isinstance(new, str) or not old or old not in text:
        return None
    return text.replace(old, new) if every is True else text.replace(old, new, 1)


def _after_edit(target: _Target, tool: str, data: dict) -> str | None:
    """The file text once this edit applies; None when it cannot be worked out."""
    if tool == "Write":
        content = data.get("content")
        return content if isinstance(content, str) else None
    text = target.text()
    if text is None:
        return None
    edits = data.get("edits") if tool == "MultiEdit" else [data]
    if not isinstance(edits, list):
        return None
    for edit in edits:
        if not isinstance(edit, dict):
            return None
        text = _replace(
            text, edit.get("old_string"), edit.get("new_string"), edit.get("replace_all")
        )
        if text is None:
            return None
    return text


def _edit_tool(cwd: Path, tool: str, data: dict) -> str | None:
    key = "notebook_path" if tool == "NotebookEdit" else "file_path"
    target = _target(cwd, data.get(key))
    if target is None:
        return None
    if target.approved:
        return _edit_reason(target)
    if tool != "NotebookEdit":
        result = _after_edit(target, tool, data)
        if result is not None and _status(result) == "approved":
            return _forge_reason(target)
    return None


# --- Codex apply_patch ----------------------------------------------------------------------


def _apply_patch(cwd: Path, command: Any) -> str | None:
    if not isinstance(command, str):
        return None
    current: _Target | None = None
    for line in command.splitlines():
        header = _PATCH_HEADER.match(line)
        if header:
            target = _target(cwd, header.group(2).strip())
            if target is not None and target.approved:
                return _edit_reason(target)
            # A rename keeps the hunk lines under the original header; follow its destination.
            current = target if header.group(1) != "Move to" else target or current
            continue
        if line.startswith("*** "):
            current = None
        elif current is not None and _APPROVED_LINE.match(line):
            return _forge_reason(current)
    return None


# --- Bash heuristic -------------------------------------------------------------------------


def _tokens(command: str) -> list[str] | None:
    lexer = shlex.shlex(command.replace("\n", " ; "), posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    try:
        return list(lexer)
    except ValueError:
        return None


def _simple_commands(tokens: list[str]) -> list[list[str]]:
    commands: list[list[str]] = [[]]
    for token in tokens:
        if token in _SEPARATORS:
            commands.append([])
        else:
            commands[-1].append(token)
    return [command for command in commands if command]


def _plan_pieces(text: str) -> list[str]:
    """Path-like runs ending in plan.yaml, found in linear time.

    Each run extends left from an occurrence up to a stop character, never past the
    previous occurrence, so the total work stays proportional to the text.
    """
    pieces = []
    floor = 0
    index = text.find("plan.yaml")
    while index != -1:
        start = index
        while start > floor and text[start - 1] not in _PATH_STOP:
            start -= 1
        end = index + len("plan.yaml")
        pieces.append(text[start:end])
        floor = end
        index = text.find("plan.yaml", end)
    return pieces


def _expand(cwd: Path, pattern: str) -> list[str]:
    matches: list[str] = []
    for match in glob.iglob(os.path.join(cwd, os.path.expanduser(pattern))):
        if len(matches) >= MAX_GLOB_MATCHES:
            break
        matches.append(match)
    return matches


def _candidates(cwd: Path, token: str) -> list[_Target]:
    pieces = _plan_pieces(token)
    if not pieces and any(char in token for char in _GLOB_CHARS):
        pieces = [token]  # `rm *` inside a plan directory, `pl?n.yaml`, ...
    found: list[_Target] = []
    for piece in pieces:
        if any(c in piece for c in _GLOB_CHARS):
            paths = _expand(cwd, piece)
        else:
            # Also the bare name: `sed 1wplan.yaml` glues the file name to a command letter.
            paths = [piece, os.path.join(os.path.dirname(piece), "plan.yaml")]
        found.extend(target for path in paths if (target := _target(cwd, path)))
    return found


def _program(argv: list[str]) -> tuple[str, list[str]]:
    index = 0
    while index < len(argv):
        word = argv[index]
        if re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", word) or word in _PREFIXES:
            index += 1
            continue
        return os.path.basename(word), argv[index + 1 :]
    return "", []


def _reads_only(argv: list[str]) -> bool:
    name, args = _program([token for token in argv if token not in _REDIRECTS])
    if name not in _READERS:
        return False
    for option in _WRITING_OPTIONS.get(name, ()):
        short = len(option) == 2 and re.compile(rf"^-[a-zA-Z]*{option[1]}")
        if any(arg.startswith(option) or (short and short.match(arg)) for arg in args):
            return False
    return name != "git" or any(arg in _GIT_READS for arg in args[:3])


def _bash_fallback(cwd: Path, command: str) -> str | None:
    for piece in _plan_pieces(command):
        target = _target(cwd, piece)
        if target is not None and target.approved:
            return _edit_reason(target)
    return None


def _bash(cwd: Path, command: Any, depth: int = 0) -> str | None:
    if isinstance(command, list) and all(isinstance(part, str) for part in command):
        command = shlex.join(command)
    if not isinstance(command, str):
        return None
    tokens = _tokens(command)
    if tokens is None:
        return _bash_fallback(cwd, command)
    here = cwd
    for argv in _simple_commands(tokens):
        if argv[0] == "cd":
            here = _resolve(here, argv[1]) if len(argv) > 1 and "$" not in argv[1] else cwd
            continue
        readonly = _reads_only(argv)
        for index, token in enumerate(argv):
            # `bash -c "<script>"` and friends: look inside the quoted script too.
            # Scripts nested deeper than MAX_NESTING are skipped; the rest is still checked.
            deeper = " " in token and index and depth < MAX_NESTING
            nested = _bash(here, token, depth + 1) if deeper else None
            if nested:
                return nested
            for target in _candidates(here, token):
                if not target.approved:
                    continue
                redirected = index > 0 and argv[index - 1] in _REDIRECTS
                if redirected or not readonly:
                    return _edit_reason(target)
    return None


# --- entry point ----------------------------------------------------------------------------


def decide(payload: Any) -> str | None:
    """A deny reason for this PreToolUse payload, or None to let the call through."""
    if not isinstance(payload, dict):
        return None
    tool, data = payload.get("tool_name"), payload.get("tool_input")
    if not isinstance(tool, str) or not isinstance(data, dict):
        return None
    cwd_value = payload.get("cwd")
    cwd = Path(cwd_value) if isinstance(cwd_value, str) and cwd_value else Path.cwd()
    if tool in ("Edit", "MultiEdit", "Write", "NotebookEdit"):
        return _edit_tool(cwd, tool, data)
    if tool == "apply_patch":
        return _apply_patch(cwd, data.get("command"))
    if tool == "Bash":
        return _bash(cwd, data.get("command"))
    return None


GUARDED_TOOLS = {"Edit", "MultiEdit", "Write", "NotebookEdit", "apply_patch", "Bash"}


@contextmanager
def _time_budget(seconds: int) -> Iterator[None]:
    """Raise Undecidable when analysis runs too long (main thread, POSIX only)."""
    if not hasattr(signal, "SIGALRM"):
        yield
        return

    def expired(signum: int, frame: Any) -> None:
        raise Undecidable("analysis took too long")

    previous = signal.signal(signal.SIGALRM, expired)
    signal.alarm(seconds)
    try:
        yield
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, previous)


def hook_output(
    stdin: str, *, limit: int = MAX_HOOK_INPUT, budget: int = TIME_BUDGET_SECONDS
) -> str:
    """stdout for the hook: a deny decision, or empty to allow."""
    if len(stdin) > limit:
        return ""  # cut short, so it cannot be parsed
    try:
        payload = json.loads(stdin)
    except ValueError:
        return ""
    if not isinstance(payload, dict) or payload.get("tool_name") not in GUARDED_TOOLS:
        return ""
    try:
        with _time_budget(budget):
            reason = decide(payload)
    except Exception:  # noqa: BLE001 - a call the guard cannot check is not blocked
        return ""
    return "" if reason is None else _deny(reason)


def _deny(reason: str) -> str:
    decision = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }
    return json.dumps(decision, ensure_ascii=False)
