"""AI tool registry: which tools loopspec knows about, and how each one wants
its skill/command files laid out on disk.

Two independent registries, matching how differently these two concerns vary
across tools:

- `AI_TOOLS`: every registered tool gets skill files at the same uniform path
  (`<skills_dir>/skills/<name>/SKILL.md`), so this only needs a `skills_dir`.
- `COMMAND_ADAPTERS`: slash-command file placement and naming varies wildly
  per tool (project-local vs. global, colon- vs. hyphen-namespaced, Markdown
  vs. other frontmatter), so each tool that supports commands gets its own
  adapter. A tool with no adapter here simply has no slash commands
  generated for it (see `scaffold.py`).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar, Protocol


@dataclass(frozen=True)
class ToolSpec:
    id: str
    skills_dir: str


AI_TOOLS: dict[str, ToolSpec] = {
    "claude": ToolSpec(id="claude", skills_dir=".claude"),
    "codex": ToolSpec(id="codex", skills_dir=".codex"),
    "opencode": ToolSpec(id="opencode", skills_dir=".opencode"),
    "cursor": ToolSpec(id="cursor", skills_dir=".cursor"),
    "windsurf": ToolSpec(id="windsurf", skills_dir=".windsurf"),
}


@dataclass(frozen=True)
class CommandContent:
    """A tool-agnostic command body; adapters turn this into a tool-specific file."""

    id: str
    name: str
    description: str
    body: str


class ToolCommandAdapter(Protocol):
    """Knows where a given tool wants a command file, and how to format it."""

    #: Whether this tool's command names use hyphens (`/lpsx-x`) rather than a
    #: colon namespace (`/lpsx:x`) -- determines whether skill_templates'
    #: `to_hyphenated()` transform should be applied to a template's body.
    hyphenated: ClassVar[bool]

    def get_file_path(self, project_path: Path, command_id: str) -> Path: ...

    def format_file(self, content: CommandContent) -> str: ...


@dataclass(frozen=True)
class ClaudeCommandAdapter:
    """Claude Code: project-local, colon-namespaced (`/lpsx:<verb>`)."""

    hyphenated: ClassVar[bool] = False

    def get_file_path(self, project_path: Path, command_id: str) -> Path:
        return project_path / ".claude" / "commands" / "lpsx" / f"{command_id}.md"

    def format_file(self, content: CommandContent) -> str:
        return (
            "---\n"
            f"name: {content.name}\n"
            f"description: {content.description}\n"
            "---\n\n"
            f"{content.body}\n"
        )


@dataclass(frozen=True)
class CodexCommandAdapter:
    """Codex: user-global prompts dir (not project-local), hyphenated (`/lpsx-<verb>`)."""

    hyphenated: ClassVar[bool] = True

    def _codex_home(self) -> Path:
        override = os.environ.get("CODEX_HOME")
        if override:
            return Path(override)
        return Path.home() / ".codex"

    def get_file_path(self, project_path: Path, command_id: str) -> Path:
        return self._codex_home() / "prompts" / f"lpsx-{command_id}.md"

    def format_file(self, content: CommandContent) -> str:
        return f"---\ndescription: {content.description}\n---\n\n{content.body}\n"


@dataclass(frozen=True)
class HyphenatedProjectCommandAdapter:
    """Shared shape for tools that store commands project-locally under
    `.<tool_dir>/commands/`, hyphen-namespaced (`/lpsx-<verb>`): OpenCode, Cursor, Windsurf.
    """

    tool_dir: str
    hyphenated: ClassVar[bool] = True

    def get_file_path(self, project_path: Path, command_id: str) -> Path:
        return project_path / self.tool_dir / "commands" / f"lpsx-{command_id}.md"

    def format_file(self, content: CommandContent) -> str:
        return (
            "---\n"
            f"name: {content.name}\n"
            f"description: {content.description}\n"
            "---\n\n"
            f"{content.body}\n"
        )


COMMAND_ADAPTERS: dict[str, ToolCommandAdapter] = {
    "claude": ClaudeCommandAdapter(),
    "codex": CodexCommandAdapter(),
    "opencode": HyphenatedProjectCommandAdapter(tool_dir=".opencode"),
    "cursor": HyphenatedProjectCommandAdapter(tool_dir=".cursor"),
    "windsurf": HyphenatedProjectCommandAdapter(tool_dir=".windsurf"),
}


def is_registered_tool(tool_id: str) -> bool:
    return tool_id in AI_TOOLS
