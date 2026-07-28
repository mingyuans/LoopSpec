"""Built-in skill/command templates for the loopspec main loop.

Each template has exactly one body of instructions, reused for every tool's
skill file and (if the tool has a command adapter) command file — only the
command-reference naming style (`/lpsx:x` vs `/lpsx-x`) varies per tool.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .tool_registry import CommandContent

_COMMAND_REF_RE = re.compile(r"/lpsx:([A-Za-z][\w-]*)")


def to_hyphenated(text: str) -> str:
    """Rewrite `/lpsx:<verb>` command references to `/lpsx-<verb>`."""

    return _COMMAND_REF_RE.sub(lambda match: f"/lpsx-{match.group(1)}", text)


@dataclass(frozen=True)
class SkillTemplate:
    name: str
    description: str
    verb: str
    body: str


_NEW_BODY = """Create a new loopspec change.

1. Run `loopspec new <change-name> --json` (add `--schema <name>` if the \
project has multiple candidate schemas and the command asks you to pick one).
2. Run `loopspec status <change-name> --json` to see the first ready node \
and its `nextSteps`.
3. Continue with `/lpsx:continue` to drive the rest of the loop.
"""

_CONTINUE_BODY = """Advance a loopspec change by one step.

1. Run `loopspec status <change-name> --json`.
2. Read `nextSteps` -- it names exactly one `loopspec` command to run next \
(usually `loopspec instructions <node> --change <change-name> --json`, \
sometimes `loopspec rollback <change-name> --json`).
3. Run that command. If it's `instructions`, write the artifact it \
describes to `resolvedOutputPath` (or `resolvedOutputPath.pass`/`.fail` for \
a gate), then update `state.md` per the instructions.
4. Re-run `loopspec status <change-name> --json` and repeat from step 2 \
until `isComplete` is `true` or a gate is `exhausted`.

If a gate is `failed`, `nextSteps` will point you at \
`loopspec rollback <change-name> --json` first -- run it, then continue \
via `/lpsx:continue`; `loopspec instructions` for the reset nodes will \
include `priorAttempts` explaining what failed last time.
"""

_ARCHIVE_BODY = """Archive a completed loopspec change.

Run `loopspec archive <change-name> --json`. Add `--dry-run` first if you \
want to preview the destination before moving anything. The change must be \
complete, or you must pass `--exhausted`/`--include-pending-failures` for \
the applicable edge cases.
"""

_BULK_ARCHIVE_BODY = """Archive every eligible loopspec change in one pass.

Run `loopspec bulk-archive --json` (add `--dry-run` to preview candidates \
first, `--older-than <days>` to restrict by age, `--exhausted` to include \
retry-exhausted changes). Review the `candidates`/`moved` list in the \
response before trusting it ran.
"""

SKILL_TEMPLATES: list[SkillTemplate] = [
    SkillTemplate(
        name="loopspec-new",
        description="Create a new loopspec change and see its first step.",
        verb="new",
        body=_NEW_BODY,
    ),
    SkillTemplate(
        name="loopspec-continue",
        description="Advance a loopspec change by reading status.nextSteps and acting on it.",
        verb="continue",
        body=_CONTINUE_BODY,
    ),
    SkillTemplate(
        name="loopspec-archive",
        description="Archive a single completed loopspec change.",
        verb="archive",
        body=_ARCHIVE_BODY,
    ),
    SkillTemplate(
        name="loopspec-bulk-archive",
        description="Archive all eligible loopspec changes at once.",
        verb="bulk-archive",
        body=_BULK_ARCHIVE_BODY,
    ),
]


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
