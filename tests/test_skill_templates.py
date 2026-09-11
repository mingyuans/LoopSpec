from pathlib import Path

import pytest

from loopspec.builtin_resources import builtin_skills_dir
from loopspec.errors import BuiltinSkillError
from loopspec.skill_templates import (
    _COMMAND_REF_RE,
    SKILL_TEMPLATES,
    generate_command_content,
    generate_skill_content,
    load_skill_templates,
    parse_skill_file,
    to_hyphenated,
)

SKILL_FILE = """---
name: loopspec-demo
description: A demo skill.
---

Body line one.

Body line two.
"""


def write_skill(directory: Path, filename: str, text: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / filename
    path.write_text(text, encoding="utf-8")
    return path


def test_four_templates_with_correct_verbs():
    assert len(SKILL_TEMPLATES) == 4
    verbs = {t.verb for t in SKILL_TEMPLATES}
    assert verbs == {"new", "continue", "archive", "bulk-archive"}


# --------------------------------------------------------------------------- #
# loading from builtin/skills
# --------------------------------------------------------------------------- #


def test_templates_come_from_the_bundled_skill_files():
    """`SKILL_TEMPLATES` is the loaded `builtin/skills/` tree, nothing else."""

    assert SKILL_TEMPLATES == load_skill_templates()
    assert {t.verb for t in SKILL_TEMPLATES} == {
        path.stem for path in builtin_skills_dir().glob("*.md")
    }


def test_templates_load_in_filename_order():
    paths = sorted(builtin_skills_dir().glob("*.md"))
    assert [t.verb for t in SKILL_TEMPLATES] == [path.stem for path in paths]


def test_bundled_files_are_already_shaped_like_the_skill_they_generate():
    """Each `builtin/skills/<verb>.md` *is* the `SKILL.md` a tool receives.

    Keeps the authored file honest: read one and you have read what `init`
    writes, with no transformation hiding in between.
    """

    for template in SKILL_TEMPLATES:
        path = builtin_skills_dir() / f"{template.verb}.md"
        assert generate_skill_content(template) == path.read_text(encoding="utf-8")


def test_parse_reads_metadata_from_frontmatter_and_verb_from_filename(tmp_path: Path):
    template = parse_skill_file(write_skill(tmp_path, "bulk-demo.md", SKILL_FILE))

    assert template.name == "loopspec-demo"
    assert template.description == "A demo skill."
    assert template.verb == "bulk-demo"
    assert template.body == "Body line one.\n\nBody line two.\n"
    assert "---" not in template.body


def test_parse_normalises_trailing_blank_lines(tmp_path: Path):
    template = parse_skill_file(write_skill(tmp_path, "demo.md", SKILL_FILE + "\n\n"))
    assert template.body.endswith("Body line two.\n")


@pytest.mark.parametrize(
    ("case", "text"),
    [
        ("no frontmatter", "Just a body, no delimiters.\n"),
        ("unterminated frontmatter", "---\nname: x\ndescription: y\n"),
        ("frontmatter not a mapping", "---\n- name\n---\n\nBody.\n"),
        ("missing name", "---\ndescription: y\n---\n\nBody.\n"),
        ("blank name", "---\nname: '   '\ndescription: y\n---\n\nBody.\n"),
        ("missing description", "---\nname: x\n---\n\nBody.\n"),
        ("non-string description", "---\nname: x\ndescription: 7\n---\n\nBody.\n"),
        ("empty body", "---\nname: x\ndescription: y\n---\n\n\n"),
        ("invalid yaml", "---\nname: [x\n---\n\nBody.\n"),
    ],
)
def test_broken_skill_file_fails_loudly(case: str, text: str, tmp_path: Path):
    """A resource this central must never degrade into a half-empty skill."""

    path = write_skill(tmp_path, "demo.md", text)
    with pytest.raises(BuiltinSkillError) as exc_info:
        parse_skill_file(path)

    assert "demo.md" in exc_info.value.message, case
    assert exc_info.value.fix, case


def test_a_skills_dir_with_no_files_is_an_error(tmp_path: Path):
    empty = tmp_path / "skills"
    empty.mkdir()
    with pytest.raises(BuiltinSkillError) as exc_info:
        load_skill_templates(empty)
    assert str(empty) in exc_info.value.message


def test_load_ignores_non_markdown_files(tmp_path: Path):
    write_skill(tmp_path, "demo.md", SKILL_FILE)
    write_skill(tmp_path, "README.txt", "not a skill")

    templates = load_skill_templates(tmp_path)
    assert [t.verb for t in templates] == ["demo"]


def test_new_template_references_loopspec_new_command():
    template = next(t for t in SKILL_TEMPLATES if t.verb == "new")
    assert "loopspec new" in template.body


def test_new_template_reuses_canonical_name_without_schema_suffixes():
    body = next(t for t in SKILL_TEMPLATES if t.verb == "new").body
    assert "inspect existing change names" in body
    assert "same ticket key" in body
    assert "do not add" in body
    assert "returned canonical name" in body


def test_continue_template_references_status_and_nextsteps():
    template = next(t for t in SKILL_TEMPLATES if t.verb == "continue")
    assert "loopspec status" in template.body
    assert "nextSteps" in template.body


def test_no_template_calls_status_with_json():
    """`status`'s default output is already the LLM-facing report -- see D9.

    Asserted across every template rather than per template, so a `--json` added
    back to any one of them fails here.
    """

    for template in SKILL_TEMPLATES:
        for line in template.body.splitlines():
            if "loopspec status" in line:
                assert "--json" not in line, template.verb


def test_continue_template_still_calls_instructions_with_json():
    body = next(t for t in SKILL_TEMPLATES if t.verb == "continue").body
    instruction_lines = [line for line in body.splitlines() if "loopspec instructions" in line]
    assert instruction_lines
    assert any("--json" in line for line in instruction_lines)


def test_continue_template_covers_human_decisions_and_code_changes():
    body = next(t for t in SKILL_TEMPLATES if t.verb == "continue").body
    assert "ask a human for a decision" in body
    assert "change code in the repository" in body
    assert "taskProgress" in body


def test_continue_template_stays_schema_agnostic():
    body = next(t for t in SKILL_TEMPLATES if t.verb == "continue").body
    # The loop drives any schema, so it must not name built-in schema node ids.
    assert "approval" not in body
    assert "apply" not in body


def test_every_command_reference_also_names_the_skill_behind_it():
    """`forgecode`, `kimi` and `vibe` get skill files but no slash commands
    (they have no entry in `COMMAND_ADAPTERS`), so a body that only cites
    `/lpsx:<verb>` tells those users to type a command nobody wrote. Every
    reference must name the `loopspec-<verb>` skill as the way in too.
    """

    for template in SKILL_TEMPLATES:
        for verb in set(_COMMAND_REF_RE.findall(template.body)):
            assert f"loopspec-{verb}" in template.body, f"{template.verb} -> /lpsx:{verb}"


def test_skill_names_survive_the_hyphen_transform():
    """`to_hyphenated` targets `/lpsx:x` only -- a `loopspec-continue` skill
    name sitting in the same sentence must come through untouched."""

    template = next(t for t in SKILL_TEMPLATES if t.verb == "continue")
    content = generate_command_content(template, apply_hyphen_transform=True)
    assert "loopspec-continue" in content.body


def test_to_hyphenated_rewrites_command_references():
    text = "Continue via `/lpsx:continue` after rollback."
    assert to_hyphenated(text) == "Continue via `/lpsx-continue` after rollback."


def test_to_hyphenated_leaves_unrelated_text_untouched():
    text = "Nothing to transform here: just plain prose about loopspec."
    assert to_hyphenated(text) == text


def test_to_hyphenated_transforms_multiple_references():
    text = "First run `/lpsx:new`, then `/lpsx:continue`."
    assert to_hyphenated(text) == "First run `/lpsx-new`, then `/lpsx-continue`."


def test_generate_skill_content_has_frontmatter_and_body():
    template = SKILL_TEMPLATES[0]
    content = generate_skill_content(template)
    assert content.startswith("---\n")
    assert f"name: {template.name}" in content
    assert template.body in content


def test_generate_command_content_claude_keeps_colon_naming():
    template = next(t for t in SKILL_TEMPLATES if t.verb == "continue")
    content = generate_command_content(template, apply_hyphen_transform=False)
    assert content.name == "/lpsx:continue"
    assert "/lpsx:continue" in content.body


def test_generate_command_content_hyphenated_tools_transform_naming():
    template = next(t for t in SKILL_TEMPLATES if t.verb == "continue")
    content = generate_command_content(template, apply_hyphen_transform=True)
    assert content.name == "/lpsx-continue"
    assert "/lpsx-continue" in content.body
    assert "/lpsx:continue" not in content.body
