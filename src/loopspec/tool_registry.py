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
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar, Protocol


@dataclass(frozen=True)
class ToolSpec:
    id: str
    skills_dir: str
    #: Human-readable name for summaries and progress lines; falls back to the id.
    display_name: str | None = None
    #: Paths (relative to the project root) that mean "this tool is in use here".
    #: Any one of them existing counts. `None` falls back to `skills_dir` being a
    #: directory, which is the right test for a tool that owns its own dotdir --
    #: but wrong for one whose dotdir has other tenants, see `github-copilot`.
    detection_paths: tuple[str, ...] | None = None

    @property
    def label(self) -> str:
        return self.display_name or self.id


#: `.github` is shared with CI config, issue templates and much else, so nearly
#: every repository has one. Detecting Copilot by directory would pre-select it
#: on first-time setup everywhere and write a pile of files nobody asked for;
#: these are the paths that actually mean Copilot.
_COPILOT_DETECTION_PATHS = (
    ".github/copilot-instructions.md",
    ".github/instructions",
    ".github/prompts",
    ".github/agents",
    ".github/skills",
    ".github/.mcp.json",
)

AI_TOOLS: dict[str, ToolSpec] = {
    "amazon-q": ToolSpec(id="amazon-q", skills_dir=".amazonq", display_name="Amazon Q Developer"),
    "antigravity": ToolSpec(id="antigravity", skills_dir=".agent", display_name="Antigravity"),
    "auggie": ToolSpec(id="auggie", skills_dir=".augment", display_name="Auggie (Augment CLI)"),
    "bob": ToolSpec(id="bob", skills_dir=".bob", display_name="Bob Shell"),
    "claude": ToolSpec(id="claude", skills_dir=".claude", display_name="Claude Code"),
    "cline": ToolSpec(id="cline", skills_dir=".cline", display_name="Cline"),
    "codebuddy": ToolSpec(
        id="codebuddy", skills_dir=".codebuddy", display_name="CodeBuddy Code (CLI)"
    ),
    "codex": ToolSpec(id="codex", skills_dir=".codex", display_name="Codex"),
    "continue": ToolSpec(id="continue", skills_dir=".continue", display_name="Continue"),
    "costrict": ToolSpec(id="costrict", skills_dir=".cospec", display_name="CoStrict"),
    "crush": ToolSpec(id="crush", skills_dir=".crush", display_name="Crush"),
    "cursor": ToolSpec(id="cursor", skills_dir=".cursor", display_name="Cursor"),
    "factory": ToolSpec(id="factory", skills_dir=".factory", display_name="Factory Droid"),
    "forgecode": ToolSpec(id="forgecode", skills_dir=".forge", display_name="ForgeCode"),
    "gemini": ToolSpec(id="gemini", skills_dir=".gemini", display_name="Gemini CLI"),
    "github-copilot": ToolSpec(
        id="github-copilot",
        skills_dir=".github",
        display_name="GitHub Copilot",
        detection_paths=_COPILOT_DETECTION_PATHS,
    ),
    "iflow": ToolSpec(id="iflow", skills_dir=".iflow", display_name="iFlow"),
    "junie": ToolSpec(id="junie", skills_dir=".junie", display_name="Junie"),
    "kilocode": ToolSpec(id="kilocode", skills_dir=".kilocode", display_name="Kilo Code"),
    "kimi": ToolSpec(id="kimi", skills_dir=".kimi", display_name="Kimi CLI"),
    "kiro": ToolSpec(id="kiro", skills_dir=".kiro", display_name="Kiro"),
    "lingma": ToolSpec(id="lingma", skills_dir=".lingma", display_name="Lingma"),
    "oh-my-pi": ToolSpec(id="oh-my-pi", skills_dir=".omp", display_name="Oh My Pi"),
    "opencode": ToolSpec(id="opencode", skills_dir=".opencode", display_name="OpenCode"),
    "pi": ToolSpec(id="pi", skills_dir=".pi", display_name="Pi"),
    "qoder": ToolSpec(id="qoder", skills_dir=".qoder", display_name="Qoder"),
    "qwen": ToolSpec(id="qwen", skills_dir=".qwen", display_name="Qwen Code"),
    "roocode": ToolSpec(id="roocode", skills_dir=".roo", display_name="RooCode"),
    "trae": ToolSpec(id="trae", skills_dir=".trae", display_name="Trae"),
    "vibe": ToolSpec(id="vibe", skills_dir=".vibe", display_name="Mistral Vibe"),
    "windsurf": ToolSpec(id="windsurf", skills_dir=".windsurf", display_name="Windsurf"),
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

    @property
    def hyphenated(self) -> bool:
        """Whether this tool's command names use hyphens (`/lpsx-x`) rather than
        a colon namespace (`/lpsx:x`) -- determines whether skill_templates'
        `to_hyphenated()` transform should be applied to a template's body.

        Read-only so an implementation may satisfy it with a class attribute or
        derive it from another field, as `ProjectCommandAdapter` does.
        """

    def get_file_path(self, project_path: Path, command_id: str) -> Path: ...

    def format_file(self, content: CommandContent) -> str: ...


@dataclass(frozen=True)
class ProjectCommandAdapter:
    """Every project-local command layout, expressed as data rather than code.

    Extracting the 28 tools' on-disk layouts turned up only a handful of axes,
    so this one adapter covers all of them and adding a tool is a table row
    rather than a class. `hyphenated` is *derived* from `namespaced` on purpose:
    the command filename and the `/lpsx:x` -> `/lpsx-x` rewrite inside the body
    must never disagree, which two independent flags would eventually allow.

    Attributes:
        tool_dir: Command root, relative to the project. Usually the tool's
            `skills_dir`, but not always -- see `cline`, whose commands live in
            `.clinerules/` while its skills live in `.cline/`. Kept as its own
            field so neither can be inferred from the other (design D7).
        subdir: `commands`, `prompts` or `workflows`.
        nested: Extra path segment between `tool_dir` and `subdir`, for tools
            that want commands filed by their source (`costrict`).
        namespaced: True puts the verb in an `lpsx/` directory and names the
            command `/lpsx:<verb>`; False flattens it to `lpsx-<verb>`.
        extension: `.md`, `.toml`, `.prompt` or `.prompt.md`.
        body_format: Which of the three body layouts this tool parses.
    """

    tool_dir: str
    subdir: str = "commands"
    nested: str | None = None
    namespaced: bool = False
    extension: str = ".md"
    body_format: str = "md_frontmatter"

    @property
    def hyphenated(self) -> bool:
        return not self.namespaced

    def get_file_path(self, project_path: Path, command_id: str) -> Path:
        root = project_path / self.tool_dir
        if self.nested is not None:
            root = root / self.nested
        root = root / self.subdir
        if self.namespaced:
            return root / "lpsx" / f"{command_id}{self.extension}"
        return root / f"lpsx-{command_id}{self.extension}"

    def format_file(self, content: CommandContent) -> str:
        return FORMATTERS[self.body_format](content)


def _format_md_frontmatter(content: CommandContent) -> str:
    return (
        "---\n"
        f"name: {content.name}\n"
        f"description: {content.description}\n"
        "---\n\n"
        f"{content.body}\n"
    )


_TOML_TRIPLE_QUOTE = '"' * 3


def _format_toml(content: CommandContent) -> str:
    """TOML-bodied commands (`gemini`, `qwen`).

    The prompt is a multi-line basic string, so a triple quote or a trailing
    backslash in the body would break out of it. Neither occurs in the built-in
    templates, but the escaping is here rather than in a comment asserting it
    cannot happen.
    """

    prompt = content.body.replace("\\", "\\\\").replace(_TOML_TRIPLE_QUOTE, '\\"\\"\\"')
    return (
        f'description = "{_toml_escape(content.description)}"\n'
        f"prompt = {_TOML_TRIPLE_QUOTE}\n{prompt}{_TOML_TRIPLE_QUOTE}\n"
    )


def _toml_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _format_heading(content: CommandContent) -> str:
    """No frontmatter at all: `cline` reads the first heading as the name."""

    return f"# {content.name}\n\n{content.description}\n\n{content.body}\n"


FORMATTERS: dict[str, Callable[[CommandContent], str]] = {
    "md_frontmatter": _format_md_frontmatter,
    "toml": _format_toml,
    "heading": _format_heading,
}


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


def _project(
    tool_id: str,
    *,
    tool_dir: str | None = None,
    subdir: str = "commands",
    nested: str | None = None,
    namespaced: bool = False,
    extension: str = ".md",
    body_format: str = "md_frontmatter",
) -> ProjectCommandAdapter:
    """A project-local adapter whose command root defaults to the tool's `skills_dir`.

    The default is what all but one tool wants; `cline` passes `tool_dir`
    explicitly because its command dir genuinely differs (design D7).
    """

    return ProjectCommandAdapter(
        tool_dir=tool_dir if tool_dir is not None else AI_TOOLS[tool_id].skills_dir,
        subdir=subdir,
        nested=nested,
        namespaced=namespaced,
        extension=extension,
        body_format=body_format,
    )


#: Tools with no adapter get skill files but no commands -- `scaffold_tools`
#: reports them under `skipped_command_generation`.
COMMAND_ADAPTERS: dict[str, ToolCommandAdapter] = {
    # `commands/lpsx/<verb>.md`, colon-namespaced.
    "claude": _project("claude", namespaced=True),
    "codebuddy": _project("codebuddy", namespaced=True),
    "crush": _project("crush", namespaced=True),
    "lingma": _project("lingma", namespaced=True),
    "qoder": _project("qoder", namespaced=True),
    "gemini": _project("gemini", namespaced=True, extension=".toml", body_format="toml"),
    # `commands/lpsx-<verb>.md`, hyphenated.
    "auggie": _project("auggie"),
    "bob": _project("bob"),
    "cursor": _project("cursor"),
    "factory": _project("factory"),
    "iflow": _project("iflow"),
    "junie": _project("junie"),
    "oh-my-pi": _project("oh-my-pi"),
    "opencode": _project("opencode"),
    "roocode": _project("roocode"),
    "trae": _project("trae"),
    "qwen": _project("qwen", extension=".toml", body_format="toml"),
    "costrict": _project("costrict", nested="loopspec"),
    # `prompts/`.
    "amazon-q": _project("amazon-q", subdir="prompts"),
    "pi": _project("pi", subdir="prompts"),
    "continue": _project("continue", subdir="prompts", extension=".prompt"),
    "github-copilot": _project("github-copilot", subdir="prompts", extension=".prompt.md"),
    "kiro": _project("kiro", subdir="prompts", extension=".prompt.md"),
    # `workflows/`.
    "antigravity": _project("antigravity", subdir="workflows"),
    "kilocode": _project("kilocode", subdir="workflows"),
    "windsurf": _project("windsurf", subdir="workflows"),
    # Commands live outside the tool's own skills_dir.
    "cline": _project("cline", tool_dir=".clinerules", subdir="workflows", body_format="heading"),
    # User-global, not project-local.
    "codex": CodexCommandAdapter(),
}


def is_registered_tool(tool_id: str) -> bool:
    return tool_id in AI_TOOLS
