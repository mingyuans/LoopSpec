from loopspec.skill_templates import (
    SKILL_TEMPLATES,
    generate_command_content,
    generate_skill_content,
    to_hyphenated,
)


def test_four_templates_with_correct_verbs():
    assert len(SKILL_TEMPLATES) == 4
    verbs = {t.verb for t in SKILL_TEMPLATES}
    assert verbs == {"new", "continue", "archive", "bulk-archive"}


def test_new_template_references_loopspec_new_command():
    template = next(t for t in SKILL_TEMPLATES if t.verb == "new")
    assert "loopspec new" in template.body


def test_continue_template_references_status_and_nextsteps():
    template = next(t for t in SKILL_TEMPLATES if t.verb == "continue")
    assert "loopspec status" in template.body
    assert "nextSteps" in template.body


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
