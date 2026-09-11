"""Built-in skill/command templates for the loopspec main loop.

The instructions themselves are not here -- they are Markdown files under
`builtin/skills/`, one per command, each already shaped like the `SKILL.md` it
becomes: `name`/`description` frontmatter plus the body. This module only loads
and re-emits them.

Each template has exactly one body, reused for every tool's skill file and (if
the tool has a command adapter) command file -- only the command-reference
naming style (`/lpsx:x` vs `/lpsx-x`) varies per tool.

The command `verb` comes from the filename (`new.md` -> `new`), so the two can
never disagree; templates load in filename order.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml

from .builtin_resources import builtin_skills_dir
from .errors import BuiltinSkillError
from .tool_registry import CommandContent

_COMMAND_REF_RE = re.compile(r"/lpsx:([A-Za-z][\w-]*)")

_SKILL_FILE_RE = re.compile(r"\A---\n(?P<frontmatter>.*?)\n---\n(?P<body>.*)\Z", re.DOTALL)

_BROKEN_INSTALL_FIX = (
    "The bundled skill files are part of the loopspec install; reinstall it, "
    "or restore builtin/skills/ if you are working from a source checkout."
)


def to_hyphenated(text: str) -> str:
    """Rewrite `/lpsx:<verb>` command references to `/lpsx-<verb>`."""

    return _COMMAND_REF_RE.sub(lambda match: f"/lpsx-{match.group(1)}", text)


@dataclass(frozen=True)
class SkillTemplate:
    name: str
    description: str
    verb: str
    body: str


def _required_string(frontmatter: dict[str, object], key: str, path: Path) -> str:
    value = frontmatter.get(key)
    if not isinstance(value, str) or not value.strip():
        raise BuiltinSkillError(
            f"{path.name}: frontmatter key `{key}` must be a non-empty string",
            fix=_BROKEN_INSTALL_FIX,
        )
    return value.strip()


def parse_skill_file(path: Path) -> SkillTemplate:
    """Parse one `builtin/skills/<verb>.md` file into a template."""

    match = _SKILL_FILE_RE.match(path.read_text(encoding="utf-8"))
    if match is None:
        raise BuiltinSkillError(
            f"{path.name}: expected YAML frontmatter delimited by `---` lines",
            fix=_BROKEN_INSTALL_FIX,
        )

    try:
        frontmatter = yaml.safe_load(match.group("frontmatter"))
    except yaml.YAMLError as exc:
        raise BuiltinSkillError(
            f"{path.name}: frontmatter is not valid YAML: {exc}", fix=_BROKEN_INSTALL_FIX
        ) from exc
    if not isinstance(frontmatter, dict):
        raise BuiltinSkillError(
            f"{path.name}: frontmatter must be a YAML mapping", fix=_BROKEN_INSTALL_FIX
        )

    # Normalised to exactly one trailing newline: the body is re-emitted into
    # generated files, whose own formatters append their separators.
    body = match.group("body").strip("\n")
    if not body:
        raise BuiltinSkillError(f"{path.name}: body is empty", fix=_BROKEN_INSTALL_FIX)

    return SkillTemplate(
        name=_required_string(frontmatter, "name", path),
        description=_required_string(frontmatter, "description", path),
        verb=path.stem,
        body=f"{body}\n",
    )


def load_skill_templates(skills_dir: Path | None = None) -> list[SkillTemplate]:
    """Load every bundled skill template, in filename order."""

    directory = builtin_skills_dir() if skills_dir is None else skills_dir
    paths = sorted(directory.glob("*.md"))
    if not paths:
        raise BuiltinSkillError(
            f"no built-in skill files found in {directory}", fix=_BROKEN_INSTALL_FIX
        )
    return [parse_skill_file(path) for path in paths]


SKILL_TEMPLATES: list[SkillTemplate] = load_skill_templates()


def generate_skill_content(template: SkillTemplate) -> str:
    return (
        "---\n"
        f"name: {template.name}\n"
        f"description: {template.description}\n"
        "---\n\n"
        f"{template.body}"
    )


def generate_command_content(
    template: SkillTemplate, apply_hyphen_transform: bool
) -> CommandContent:
    body = to_hyphenated(template.body) if apply_hyphen_transform else template.body
    name = f"/lpsx-{template.verb}" if apply_hyphen_transform else f"/lpsx:{template.verb}"
    return CommandContent(id=template.verb, name=name, description=template.description, body=body)
