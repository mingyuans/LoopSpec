import io

import pytest
from rich.console import Console

from loopspec.presentation import (
    GLYPHS_ASCII,
    GLYPHS_UNICODE,
    Presenter,
    render_init_summary,
    sanitize,
)


def make_presenter(**console_kwargs) -> tuple[Presenter, io.StringIO]:
    stream = io.StringIO()
    console = Console(
        file=stream,
        no_color=True,
        force_terminal=False,
        width=200,
        **console_kwargs,
    )
    return Presenter(console, ascii_only=False), stream


# --------------------------------------------------------------------------- #
# D10: user-controlled strings must survive rendering untouched (task 1.7)
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("path", ["/tmp/[red]out/config.yaml", "/tmp/[oops]/config.yaml"])
def test_markup_like_paths_are_rendered_verbatim(path: str):
    """Unescaped, rich would silently drop `[red]` and print a path that doesn't exist."""

    presenter, stream = make_presenter()
    presenter.line(f"Config: {path}")
    assert path in stream.getvalue()


@pytest.mark.parametrize("path", ["/tmp/[/]out", "/tmp/[/bold]out"])
def test_closing_tag_paths_do_not_raise(path: str):
    """Unescaped, these raise rich.errors.MarkupError and abort the command."""

    presenter, stream = make_presenter()
    presenter.line(presenter.success(path))
    assert path in stream.getvalue()


def test_markup_like_paths_survive_every_helper():
    path = "/tmp/[red]out"
    presenter, stream = make_presenter()
    presenter.line(presenter.heading(path))
    presenter.line(presenter.success(path))
    presenter.line(presenter.failure(path))
    presenter.line(presenter.warning(path))
    presenter.line(presenter.ready(path))
    presenter.line(presenter.dim(path))
    presenter.line(presenter.bullet(path))
    presenter.line(presenter.link("Learn more: ", path))
    presenter.line(presenter.indented(path))
    assert stream.getvalue().count(path) == 9


def test_nested_helper_output_is_not_double_escaped():
    """A helper's output is final: no literal backslash-bracket leaks through."""

    presenter, stream = make_presenter()
    presenter.line(presenter.bullet("/tmp/[red]out"))
    output = stream.getvalue()
    assert "/tmp/[red]out" in output
    assert "\\[" not in output


def test_control_characters_are_made_visible():
    presenter, stream = make_presenter()
    presenter.line(f"Config: /tmp/{chr(7)}bell/{chr(27)}[31mred")
    output = stream.getvalue()
    assert "\\x07" in output
    assert "\\x1b" in output
    assert chr(7) not in output
    assert chr(27) not in output


def test_sanitize_leaves_ordinary_text_alone():
    assert sanitize("/tmp/[red]out/config.yaml") == "/tmp/[red]out/config.yaml"


# --------------------------------------------------------------------------- #
# Glyph and colour vocabulary
# --------------------------------------------------------------------------- #


def test_glyph_and_style_mapping():
    presenter, stream = make_presenter()
    presenter.line(presenter.success("done"))
    presenter.line(presenter.failure("broken"))
    presenter.line(presenter.warning("careful"))
    presenter.line(presenter.ready("skeleton"))
    presenter.line(presenter.bullet("item"))
    lines = stream.getvalue().splitlines()
    assert lines[0] == "✔ done"
    assert lines[1] == "✖ broken"
    assert lines[2] == "⚠ careful"
    assert lines[3] == "▌ skeleton"
    assert lines[4] == "  • item"


def test_headings_and_dim_carry_no_glyph():
    presenter, stream = make_presenter()
    presenter.line(presenter.heading("Getting started:"))
    presenter.line(presenter.dim("Commands skipped for: kimi (no adapter)"))
    lines = stream.getvalue().splitlines()
    assert lines[0] == "Getting started:"
    assert lines[1] == "Commands skipped for: kimi (no adapter)"


def test_colour_is_applied_when_the_console_allows_it():
    stream = io.StringIO()
    presenter = Presenter(
        Console(file=stream, force_terminal=True, width=200), ascii_only=False
    )
    presenter.line(presenter.success("done"))
    assert "\x1b[" in stream.getvalue()  # some colour escape is present


def test_ascii_fallback_glyphs():
    stream = io.StringIO()
    presenter = Presenter(
        Console(file=stream, no_color=True, force_terminal=False, width=200), ascii_only=True
    )
    presenter.line(presenter.success("done"))
    presenter.line(presenter.bullet("item"))
    lines = stream.getvalue().splitlines()
    assert lines[0] == "ok done"
    assert lines[1] == "  - item"
    assert set(GLYPHS_ASCII) == set(GLYPHS_UNICODE)


def test_ascii_fallback_selected_from_output_encoding():
    class AsciiStream(io.StringIO):
        encoding = "ascii"

    presenter = Presenter(Console(file=AsciiStream(), no_color=True, force_terminal=False))
    assert presenter.glyphs == GLYPHS_ASCII


def test_unicode_glyphs_selected_for_utf8_encoding():
    class Utf8Stream(io.StringIO):
        encoding = "utf-8"

    presenter = Presenter(Console(file=Utf8Stream(), no_color=True, force_terminal=False))
    assert presenter.glyphs == GLYPHS_UNICODE


# --------------------------------------------------------------------------- #
# Environment degradation
# --------------------------------------------------------------------------- #


def test_no_ansi_sequences_when_not_a_terminal():
    presenter, stream = make_presenter()
    presenter.line(presenter.success("done"))
    presenter.line(presenter.link("Learn more: ", "https://example.com"))
    assert "\x1b[" not in stream.getvalue()


def test_no_color_env_strips_colour_but_keeps_text(monkeypatch):
    monkeypatch.setenv("NO_COLOR", "1")
    stream = io.StringIO()
    presenter = Presenter(Console(file=stream, force_terminal=True, width=200), ascii_only=False)
    presenter.line(presenter.success("done"))
    output = stream.getvalue()
    assert "✔ done" in output
    assert "\x1b[3" not in output  # no colour codes


def test_stage_without_terminal_emits_plain_completion_line():
    presenter, stream = make_presenter()
    with presenter.stage("Writing files...", "Setup complete for Claude Code"):
        pass
    output = stream.getvalue()
    assert output == "✔ Setup complete for Claude Code\n"
    assert "\x1b[" not in output  # no cursor control noise


def test_stage_in_terminal_still_leaves_the_completion_line():
    stream = io.StringIO()
    presenter = Presenter(
        Console(file=stream, force_terminal=True, no_color=True, width=200), ascii_only=False
    )
    with presenter.stage("Writing files...", "Setup complete for Codex"):
        pass
    assert "✔ Setup complete for Codex" in stream.getvalue()


# --------------------------------------------------------------------------- #
# init summary
# --------------------------------------------------------------------------- #


def summary_output(**overrides) -> str:
    presenter, stream = make_presenter()
    kwargs = {
        "created": ["Claude Code"],
        "refreshed": ["Codex"],
        "skill_count": 8,
        "command_count": 8,
        "tool_dirs": [".claude", ".codex"],
        "skipped_command_generation": [],
        "config_path": "loopspec/config.yaml",
        "schema_name": "secure-spec-driven",
        "getting_started": "loopspec new <change-name>",
        "project_url": "https://github.com/mingyuans/LoopSpec",
        "issues_url": "https://github.com/mingyuans/LoopSpec/issues",
    }
    kwargs.update(overrides)
    render_init_summary(presenter, **kwargs)
    return stream.getvalue()


def test_summary_section_order():
    lines = [line for line in summary_output().splitlines() if line.strip()]
    assert lines == [
        "LoopSpec Setup Complete",
        "Created: Claude Code",
        "Refreshed: Codex",
        "8 skills and 8 commands in .claude, .codex",
        "Config: loopspec/config.yaml (schema: secure-spec-driven)",
        "Getting started:",
        "  loopspec new <change-name>",
        "Learn more: https://github.com/mingyuans/LoopSpec",
        "Feedback:   https://github.com/mingyuans/LoopSpec/issues",
        "Restart your IDE for slash commands to take effect.",
    ]


def test_summary_never_lists_file_paths():
    output = summary_output()
    assert "SKILL.md" not in output
    assert ".claude/skills" not in output


def test_summary_omits_empty_created_or_refreshed_lines():
    output = summary_output(refreshed=[])
    assert "Created:" in output
    assert "Refreshed:" not in output


def test_summary_config_exists_variant():
    output = summary_output(schema_name=None)
    assert "Config: loopspec/config.yaml (exists)" in output
    assert "schema:" not in output


def test_summary_reports_tools_without_a_command_adapter():
    output = summary_output(skipped_command_generation=["kimi"])
    assert "Commands skipped for: kimi (no adapter)" in output


def test_summary_without_tools_skips_counts_and_restart_hint():
    output = summary_output(created=[], refreshed=[], tool_dirs=[], skill_count=0, command_count=0)
    assert "skills and" not in output
    assert "Restart your IDE" not in output
    assert "Getting started:" in output


def test_summary_singularizes_counts():
    output = summary_output(skill_count=1, command_count=1)
    assert "1 skill and 1 command in" in output


def test_summary_contains_no_emoji_or_box_drawing():
    output = summary_output()
    assert not any(ord(char) > 0x2500 for char in output), "no box drawing or emoji allowed"
    assert "|" not in output and "+" not in output


def test_summary_escapes_user_controlled_paths():
    output = summary_output(config_path="/tmp/[red]out/config.yaml")
    assert "/tmp/[red]out/config.yaml" in output
