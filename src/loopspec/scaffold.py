"""Write AI-tool skill/command files for a project.

Always overwrites: a tool's skill/command files are unconditionally
rewritten on every call, with no diffing, no per-file confirmation, and no
persisted record of "which tools were selected" -- whether a tool is
configured is always answered by checking whether its files exist on disk.
"""

from __future__ import annotations

import json
import os
import stat
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .skill_templates import SKILL_TEMPLATES, generate_command_content, generate_skill_content
from .tool_registry import AI_TOOLS, COMMAND_ADAPTERS


@dataclass
class ScaffoldResult:
    written_files: dict[str, list[str]] = field(default_factory=dict)
    skipped_command_generation: list[str] = field(default_factory=list)
    #: Tools scaffolded for the first time vs. tools whose files were overwritten.
    #: Captured *before* writing -- see `scaffold_tools`.
    created: list[str] = field(default_factory=list)
    refreshed: list[str] = field(default_factory=list)


def tool_is_configured(project_path: Path, tool_id: str) -> bool:
    """Whether this tool already has skill files on disk.

    The only source of truth for "is this tool configured" -- there is no
    persisted record of past selections to consult.
    """

    tool = AI_TOOLS[tool_id]
    skills_root = project_path / tool.skills_dir / "skills"
    return any((skills_root / template.name / "SKILL.md").is_file() for template in SKILL_TEMPLATES)


def scaffold_tools(project_path: Path, tool_ids: list[str]) -> ScaffoldResult:
    """Write skill files (all tools) and command files (tools with an adapter)."""

    result = ScaffoldResult()

    for tool_id in tool_ids:
        tool = AI_TOOLS[tool_id]
        written: list[str] = []

        # Writing is an unconditional overwrite, so "was this already here?" can
        # only be answered before the first write.
        if tool_is_configured(project_path, tool_id):
            result.refreshed.append(tool_id)
        else:
            result.created.append(tool_id)

        skills_root = project_path / tool.skills_dir / "skills"
        for template in SKILL_TEMPLATES:
            skill_path = skills_root / template.name / "SKILL.md"
            skill_path.parent.mkdir(parents=True, exist_ok=True)
            skill_path.write_text(generate_skill_content(template), encoding="utf-8")
            written.append(str(skill_path))

        adapter = COMMAND_ADAPTERS.get(tool_id)
        if adapter is None:
            result.skipped_command_generation.append(tool_id)
        else:
            for template in SKILL_TEMPLATES:
                content = generate_command_content(
                    template, apply_hyphen_transform=adapter.hyphenated
                )
                command_path = adapter.get_file_path(project_path, template.verb)
                command_path.parent.mkdir(parents=True, exist_ok=True)
                command_path.write_text(adapter.format_file(content), encoding="utf-8")
                written.append(str(command_path))

        result.written_files[tool_id] = written

    return result


HOOK_COMMAND = "loopspec hook pre-tool-use"
#: Project-level hook config per tool, and the tool names its PreToolUse matcher covers.
#: Codex reports every file edit as `apply_patch` and shell commands as `Bash`.
HOOK_TARGETS = {
    "claude": (".claude/settings.json", "Edit|MultiEdit|Write|NotebookEdit|Bash"),
    "codex": (".codex/hooks.json", "^apply_patch$|^Bash$"),
}


def _merged_hooks(data: Any, matcher: str) -> dict | str | None:
    """The config with our hook added; None when already present; a str says why not."""
    if not isinstance(data, dict):
        return "not a JSON object"
    hooks = data.get("hooks", {})
    if not isinstance(hooks, dict):
        return "`hooks` is not an object"
    entries = hooks.get("PreToolUse", [])
    if not isinstance(entries, list):
        return "`hooks.PreToolUse` is not a list"
    for entry in entries:
        handlers = entry.get("hooks") if isinstance(entry, dict) else None
        if isinstance(handlers, list) and any(
            isinstance(handler, dict) and handler.get("command") == HOOK_COMMAND
            for handler in handlers
        ):
            return None
    entry = {"matcher": matcher, "hooks": [{"type": "command", "command": HOOK_COMMAND}]}
    return {**data, "hooks": {**hooks, "PreToolUse": [*entries, entry]}}


def _install_hook(project_path: Path, relative: str, matcher: str) -> dict:
    path = project_path / relative
    result: dict = {"path": str(path)}
    try:
        info = path.lstat()
    except FileNotFoundError:
        data: Any = {}
        status = "created"
    else:
        if not stat.S_ISREG(info.st_mode):
            return {**result, "status": "skipped", "reason": "not a regular file"}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, UnicodeError):
            return {**result, "status": "skipped", "reason": "not valid JSON"}
        status = "updated"
    merged = _merged_hooks(data, matcher)
    if merged is None:
        return {**result, "status": "unchanged"}
    if isinstance(merged, str):
        return {**result, "status": "skipped", "reason": merged}
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix=".loopspec-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(json.dumps(merged, ensure_ascii=False, indent=2) + "\n")
        os.replace(temporary, path)
    except BaseException:
        os.unlink(temporary)
        raise
    return {**result, "status": status}


def install_hooks(project_path: Path, tool_ids: list[str]) -> dict[str, dict]:
    """Merge the plan-guard PreToolUse hook into each selected tool's project config.

    Unlike skill files this never overwrites: existing settings and hooks are kept,
    and a config we cannot parse is left alone and reported as skipped.
    """

    return {
        tool_id: _install_hook(project_path, *HOOK_TARGETS[tool_id])
        for tool_id in tool_ids
        if tool_id in HOOK_TARGETS
    }
