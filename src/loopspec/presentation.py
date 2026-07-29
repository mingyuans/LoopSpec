"""The single source of loopspec's human-readable output vocabulary.

**Human-readable paths only.** Nothing here may be used on a `--json` code path:
the JSON protocol must stay byte-for-byte free of styling, progress and glyphs.
That is why no function in this module takes an `as_json` flag -- a JSON path
cannot reach for these helpers by accident.

**Escaping is structural, not a calling convention.** Every public helper takes
raw strings and returns a `rich.text.Text` object, which rich renders literally --
console markup is never parsed. Callers therefore pass user-controlled values
(paths, schema names) directly and cannot get it wrong; there is no `escape()`
call for a caller to forget, and no double-escaping hazard from nesting helpers.
Control characters are additionally rewritten to a visible `\\xNN` form so a
crafted path cannot inject cursor movement or colour resets into the output.

Without that guarantee, rich's default markup parsing would treat a path like
`/tmp/[red]out/config.yaml` as styling and silently print `/tmp/out/config.yaml`
-- a path that does not exist, with no error -- while `/tmp/[/]out` would raise
`MarkupError` and abort the command.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from contextlib import contextmanager

from rich.console import Console
from rich.text import Text

#: Semantic name -> glyph, with an ASCII fallback for encodings that cannot
#: represent them (CI logs, redirected output, legacy Windows code pages).
GLYPHS_UNICODE: dict[str, str] = {
    "success": "✔",  # heavy check mark
    "failure": "✖",  # heavy multiplication x
    "warning": "⚠",  # warning sign
    "bullet": "•",  # bullet
    "ready": "▌",  # left half block
}

GLYPHS_ASCII: dict[str, str] = {
    "success": "ok",
    "failure": "x",
    "warning": "!",
    "bullet": "-",
    "ready": "|",
}

STYLES: dict[str, str] = {
    "success": "green",
    "failure": "red",
    "warning": "yellow",
    "ready": "bright_white",
    "heading": "bold",
    "dim": "dim",
    "link": "cyan",
    "logo": "bright_cyan",
}

INDENT = "  "

#: The welcome logo, as one static frame. Deliberately not a list of frames and
#: deliberately not paired with any redraw helper: an animated logo was ruled
#: out, and the cheapest way to keep it ruled out is to have nothing here that
#: could drive one.
#: Glyphs are a uniform 4 columns wide, separated by one space, so the rows line
#: up: L O O P S P E C.
LOGO_UNICODE: tuple[str, ...] = (
    "█    ▄▀▀▄ ▄▀▀▄ █▀▀▄ ▄▀▀▀ █▀▀▄ █▀▀▀ ▄▀▀▀",
    "█    █  █ █  █ █▀▀  ▀▀▀▄ █▀▀  █▀▀  █   ",
    "▀▀▀▀ ▀▄▄▀ ▀▄▄▀ █    ▄▄▄▀ █    ▀▀▀▀ ▀▄▄▄",
)

#: Same word, in characters every code page can encode.
LOGO_ASCII: tuple[str, ...] = (
    "|     __   __   __   __   __   ___  __ ",
    "|    |  | |  | |__| |__  |__| |__  |   ",
    "|___ |__| |__| |     __| |    |___ |__ ",
)

_CONTROL_RE = re.compile(r"[\x00-\x1f\x7f-\x9f]")


def sanitize(value: object) -> str:
    """Render control characters visibly so they cannot rewrite the terminal."""

    return _CONTROL_RE.sub(lambda match: f"\\x{ord(match.group()):02x}", str(value))


def encoding_supports(encoding: str | None, sample: str) -> bool:
    try:
        sample.encode(encoding or "utf-8")
    except (UnicodeEncodeError, LookupError):
        return False
    return True


class Presenter:
    """Owns a `Console` and turns raw strings into styled, escaped output.

    The console is injectable so tests can pin `no_color`/`force_terminal` and
    assert on plain text.
    """

    def __init__(self, console: Console | None = None, *, ascii_only: bool | None = None) -> None:
        self.console = console if console is not None else Console()
        if ascii_only is None:
            encoding = getattr(self.console.file, "encoding", None)
            sample = "".join(GLYPHS_UNICODE.values()) + "".join(LOGO_UNICODE)
            ascii_only = not encoding_supports(encoding, sample)
        self.glyphs = GLYPHS_ASCII if ascii_only else GLYPHS_UNICODE
        self.logo = LOGO_ASCII if ascii_only else LOGO_UNICODE

    # -- formatting ------------------------------------------------------- #

    def _glyph_line(self, kind: str, text: str) -> Text:
        return Text(f"{self.glyphs[kind]} ", style=STYLES[kind]).append(
            Text(sanitize(text), style="")
        )

    def heading(self, text: str) -> Text:
        """A section title: bold, no glyph."""

        return Text(sanitize(text), style=STYLES["heading"])

    def success(self, text: str) -> Text:
        return self._glyph_line("success", text)

    def failure(self, text: str) -> Text:
        return self._glyph_line("failure", text)

    def warning(self, text: str) -> Text:
        return self._glyph_line("warning", text)

    def ready(self, text: str) -> Text:
        """Structure-is-in-place marker for a completed setup step."""

        return self._glyph_line("ready", text)

    def dim(self, text: str) -> Text:
        """Secondary/skipped information: dim, no glyph."""

        return Text(sanitize(text), style=STYLES["dim"])

    def bullet(self, text: str) -> Text:
        return Text(f"{INDENT}{self.glyphs['bullet']} ").append(Text(sanitize(text)))

    def link(self, label: str, url: str) -> Text:
        return Text(sanitize(label)).append(Text(sanitize(url), style=STYLES["link"]))

    def indented(self, text: str) -> Text:
        return Text(f"{INDENT}{sanitize(text)}")

    def logo_lines(self) -> list[Text]:
        """The static logo, one `Text` per row.

        Returns rows rather than printing them so the caller controls spacing --
        and so there is no redraw-in-place entry point to reach for later.
        """

        return [Text(row, style=STYLES["logo"]) for row in self.logo]

    # -- output ----------------------------------------------------------- #

    def line(self, item: Text | str = "") -> None:
        """Print one line. `soft_wrap` keeps long paths and URLs intact."""

        renderable = item if isinstance(item, Text) else Text(sanitize(item))
        self.console.print(renderable, soft_wrap=True)

    def blank(self) -> None:
        self.console.print()

    @contextmanager
    def stage(self, running: str, done: str) -> Iterator[None]:
        """Show progress for one step, then leave a completion line behind.

        In a terminal this is a spinner; anywhere else the spinner is skipped
        entirely so redirected output carries no cursor-control noise.
        """

        if self.console.is_terminal:
            with self.console.status(Text(sanitize(running))):
                yield
        else:
            yield
        self.line(self.success(done))


WELCOME_TITLE = "Welcome to LoopSpec"
WELCOME_SUBTITLE = "A gated artifact workflow for spec-driven development"

WELCOME_CONFIGURES: tuple[str, ...] = (
    "Agent Skills for AI tools",
    "/lpsx:* slash commands",
)

#: Verb -> one-line purpose. Verbs must match the commands `init` actually
#: writes (see `skill_templates.SKILL_TEMPLATES`) -- a quick start that lists a
#: command the user cannot type is worse than no quick start. `test_presentation`
#: pins the two together.
WELCOME_QUICK_START: tuple[tuple[str, str], ...] = (
    ("new", "Create a change"),
    ("continue", "Advance to the next artifact"),
    ("archive", "Archive a finished change"),
)

WELCOME_PROMPT = "Press Enter to select tools..."


def render_welcome(presenter: Presenter) -> None:
    """Render `init`'s opening screen, in a fixed section order.

    Only ever called on the interactive path: it ends by telling the user to
    press Enter for the tool picker, so rendering it without a picker to follow
    would be lying to them. `init` computes that condition once and uses it for
    both (design D3).
    """

    presenter.blank()
    for row in presenter.logo_lines():
        presenter.line(row)
    presenter.blank()

    presenter.line(presenter.heading(WELCOME_TITLE))
    presenter.line(WELCOME_SUBTITLE)
    presenter.blank()

    presenter.line("This setup will configure:")
    for item in WELCOME_CONFIGURES:
        presenter.line(presenter.bullet(item))
    presenter.blank()

    presenter.line("Quick start after setup:")
    width = max(len(verb) for verb, _ in WELCOME_QUICK_START) + len("/lpsx:")
    for verb, purpose in WELCOME_QUICK_START:
        presenter.line(presenter.indented(f"{f'/lpsx:{verb}':<{width}}  {purpose}"))
    presenter.blank()

    presenter.line(presenter.dim(WELCOME_PROMPT))


def render_init_summary(
    presenter: Presenter,
    *,
    created: list[str],
    refreshed: list[str],
    skill_count: int,
    command_count: int,
    tool_dirs: list[str],
    skipped_command_generation: list[str],
    config_path: str,
    schema_name: str | None,
    getting_started: str,
    project_url: str,
    issues_url: str,
) -> None:
    """Render `loopspec init`'s success summary in a fixed section order.

    `schema_name is None` means the config file was already there and was left
    alone. Every value is passed raw: `Presenter` escapes it.

    No `as_json` parameter by design -- see the module docstring.
    """

    presenter.blank()
    presenter.line(presenter.heading("LoopSpec Setup Complete"))
    presenter.blank()

    if created:
        presenter.line(f"Created: {', '.join(created)}")
    if refreshed:
        presenter.line(f"Refreshed: {', '.join(refreshed)}")

    if tool_dirs:
        skills = "skill" if skill_count == 1 else "skills"
        commands = "command" if command_count == 1 else "commands"
        presenter.line(
            f"{skill_count} {skills} and {command_count} {commands} in {', '.join(tool_dirs)}"
        )

    if skipped_command_generation:
        presenter.line(
            presenter.dim(
                f"Commands skipped for: {', '.join(skipped_command_generation)} (no adapter)"
            )
        )

    presenter.blank()
    if schema_name is None:
        presenter.line(f"Config: {config_path} (exists)")
    else:
        presenter.line(f"Config: {config_path} (schema: {schema_name})")

    presenter.blank()
    presenter.line(presenter.heading("Getting started:"))
    presenter.line(presenter.indented(getting_started))

    presenter.blank()
    presenter.line(presenter.link("Learn more: ", project_url))
    presenter.line(presenter.link("Feedback:   ", issues_url))

    if created or refreshed:
        presenter.blank()
        presenter.line("Restart your IDE for slash commands to take effect.")
