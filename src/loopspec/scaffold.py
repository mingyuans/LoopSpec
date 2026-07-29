"""Write AI-tool skill/command files for a project.

Always overwrites: a tool's skill/command files are unconditionally
rewritten on every call, with no diffing, no per-file confirmation, and no
persisted record of "which tools were selected" -- whether a tool is
configured is always answered by checking whether its files exist on disk.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

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
