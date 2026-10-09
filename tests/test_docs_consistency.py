"""Docs/code consistency, and equivalence between the two language versions.

Two independent kinds of assertion, per `specs/usage-docs`:

1. **Code -> docs, one-way.** Every command, option, model field and error code
   that exists in the code must be documented, run once per language. The
   reverse is deliberately *not* asserted: the manual legitimately documents
   things the CLI surface does not expose (`NO_COLOR`, directory conventions,
   glossary terms), so a reverse check would false-positive forever.
2. **Language vs language, two-way.** Limited to closed sets -- file lists,
   command section titles, field names, error codes -- plus equivalent example
   blocks. Configuration examples are byte-identical; workflow examples may
   localize descriptive text while keeping their structure and identifiers identical.

Everything is text parsing plus Pydantic validation. Shell blocks in the docs
are never executed, and the one check that materialises files does so only under
pytest's `tmp_path`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import pytest
import yaml
from pydantic import BaseModel
from typer.main import get_command

from loopspec import cli as cli_mod
from loopspec import errors as errors_mod
from loopspec.builtin_resources import builtin_root
from loopspec.models import GateOutputs, GateTemplates, RegistrySpec, WorkflowConfig
from loopspec.registry_sync import DefinitionVersion, RegistryLock
from loopspec.workflow_attempts import AttemptRecord, Move
from loopspec.workflow_models import (
    AssuranceRule,
    AssuranceRules,
    ChangeState,
    CodeEvidence,
    FailurePolicy,
    Fragment,
    FragmentRef,
    Node,
    PlanDocument,
    PlanMeta,
    PlanRequest,
    PlanSpec,
    Profile,
    ProjectWorkflow,
    ResolvedGate,
    ResolvedNode,
    WorkflowGate,
)
from loopspec.workflow_planning import compile_request, spec_digest

DOCS = Path(__file__).resolve().parent.parent / "docs"
LANGUAGES = ("en", "zh")

#: The files every language version must provide, relative to its dir.
REQUIRED_PAGES = (
    "README.md",
    "overview.md",
    "fragment-profile-plan.md",
    "workflow-composition.md",
    "plan-reference.md",
    "configuration.md",
    "cli-reference.md",
    "agent-protocol.md",
    "release-notes.md",
)

#: Field-table headers per language. Field *names* are located by column
#: position, never by header text -- this map only asserts the headers
#: themselves are the agreed ones, so the two versions stay comparable.
FIELD_TABLE_HEADERS = {
    "en": ("Field", "Type", "Required", "Default", "Description"),
    "zh": ("字段", "类型", "必填", "默认值", "说明"),
}

#: Which pages carry the field tables for which models.
MODEL_PAGES = {
    "configuration.md": (
        WorkflowConfig,
        ProjectWorkflow,
        RegistrySpec,
        RegistryLock,
        DefinitionVersion,
        AssuranceRules,
        AssuranceRule,
    ),
    "workflow-composition.md": (
        Fragment,
        Node,
        WorkflowGate,
        GateOutputs,
        GateTemplates,
        CodeEvidence,
        FailurePolicy,
        Profile,
        FragmentRef,
        PlanRequest,
    ),
    "plan-reference.md": (
        PlanDocument,
        PlanMeta,
        PlanSpec,
        ResolvedNode,
        ResolvedGate,
        ChangeState,
        AttemptRecord,
        Move,
    ),
}

#: Text that must not survive anywhere in the manual or README except the release notes.
REMOVED_SURFACE = (
    "loopspec schemas",
    "loopspec new ",
    "loopspec status",
    "loopspec instructions",
    "loopspec rollback",
    "loopspec bulk-archive",
    "loopspec recover",
    "loopspec plans",
    "loopspec fragments",
    "loopspec profiles",
    "loopspec assurance",
    "--expected-digest",
    "--safety-expansion",
    "manual-v1",
    "secure-spec-driven",
    "schema.yaml",
    "min_engine_version",
    "`interrupted`",
    "open_plan",
    "active_plan",
    "next_plan",
)

EXAMPLE_MARKER = re.compile(r"<!--\s*loopspec:example=([a-z-]+)\s*-->")
FENCE = re.compile(r"^```(\S*)\s*$")
TABLE_ROW = re.compile(r"^\|(.+)\|\s*$")
CODE_SPAN = re.compile(r"^`([^`]+)`$")
COMMAND_HEADING = re.compile(r"^##\s+loopspec\s+(.+?)\s*$")
MD_LINK = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
#: First-screen lines: scope, audience, and the link to the other language.
FIRST_SCREEN_LINES = 8


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class CodeBlock:
    language: str
    marker: str | None
    body: str
    start_line: int


def page(lang: str, relative: str) -> Path:
    return DOCS / lang / relative


def read(lang: str, relative: str) -> str:
    return page(lang, relative).read_text(encoding="utf-8")


def language_pages(lang: str) -> list[Path]:
    return sorted((DOCS / lang).rglob("*.md"))


def strip_fenced(text: str) -> str:
    """Drop fenced code blocks, so prose checks never inspect examples."""

    out, in_fence = [], False
    for line in text.splitlines():
        if FENCE.match(line.strip()):
            in_fence = not in_fence
            continue
        if not in_fence:
            out.append(line)
    return "\n".join(out)


def code_blocks(text: str) -> list[CodeBlock]:
    """Every fenced block, tagged with the `loopspec:example=` marker above it."""

    blocks: list[CodeBlock] = []
    lines = text.splitlines()
    pending_marker: str | None = None
    index = 0
    while index < len(lines):
        marker_match = EXAMPLE_MARKER.match(lines[index].strip())
        if marker_match:
            pending_marker = marker_match.group(1)
            index += 1
            continue
        fence = FENCE.match(lines[index].strip())
        if not fence:
            if lines[index].strip():
                pending_marker = None
            index += 1
            continue
        start = index
        body: list[str] = []
        index += 1
        while index < len(lines) and not FENCE.match(lines[index].strip()):
            body.append(lines[index])
            index += 1
        blocks.append(
            CodeBlock(
                language=fence.group(1),
                marker=pending_marker,
                body="\n".join(body),
                start_line=start + 1,
            )
        )
        pending_marker = None
        index += 1
    return blocks


def table_rows(text: str) -> list[list[str]]:
    """Rows of every markdown table, as trimmed cell lists, ignoring examples."""

    rows: list[list[str]] = []
    for line in strip_fenced(text).splitlines():
        match = TABLE_ROW.match(line.strip())
        if not match:
            continue
        cells = [cell.strip() for cell in match.group(1).split("|")]
        if all(set(cell) <= {"-", ":"} and cell for cell in cells):
            continue  # separator row
        rows.append(cells)
    return rows


def field_table_names(text: str) -> set[str]:
    """First-column identifiers of five-column field tables.

    Position-based on purpose: a name mentioned only in prose does not count as
    documented, and the header language must not affect extraction.
    """

    header_sets = [set(headers) for headers in FIELD_TABLE_HEADERS.values()]
    names: set[str] = set()
    current_is_field_table = False
    for cells in table_rows(text):
        if len(cells) == 5 and set(cells) in header_sets:
            current_is_field_table = True
            continue
        if len(cells) != 5:
            current_is_field_table = False
            continue
        if not current_is_field_table:
            continue
        span = CODE_SPAN.match(cells[0])
        if span:
            names.add(span.group(1))
    return names


def first_column_identifiers(text: str) -> set[str]:
    """Every backticked first-column cell of every table on a page."""

    names: set[str] = set()
    for cells in table_rows(text):
        span = CODE_SPAN.match(cells[0])
        if span:
            names.add(span.group(1))
    return names


def command_sections(text: str) -> dict[str, str]:
    """`## loopspec <command>` heading to that section's body text."""

    sections: dict[str, str] = {}
    current: str | None = None
    buffer: list[str] = []
    for line in text.splitlines():
        heading = COMMAND_HEADING.match(line)
        if heading:
            if current is not None:
                sections[current] = "\n".join(buffer)
            current = heading.group(1)
            buffer = []
            continue
        if line.startswith("## ") and current is not None:
            sections[current] = "\n".join(buffer)
            current = None
            buffer = []
            continue
        if current is not None:
            buffer.append(line)
    if current is not None:
        sections[current] = "\n".join(buffer)
    return sections


def leaf_commands() -> dict[str, list[str]]:
    """Command path to its long option names, from the real CLI.

    Reached only through the public `typer.main.get_command`; `click` is not
    importable at top level under typer 0.27 (it is vendored as `typer._click`),
    and the private path must not be relied on either.
    """

    root = get_command(cli_mod.app)
    found: dict[str, list[str]] = {}

    def walk(command: object, prefix: list[str]) -> None:
        children = getattr(command, "commands", None)
        if children:
            for name, child in children.items():
                walk(child, [*prefix, name])
            return
        options = [
            opt
            for param in getattr(command, "params", [])
            for opt in getattr(param, "opts", [])
            if opt.startswith("--")
        ]
        found[" ".join(prefix)] = options

    walk(root, [])
    return found


def error_codes() -> set[str]:
    """Class-level codes plus every literal code passed to `WorkflowError`."""

    import ast

    codes: set[str] = set()
    stack = [errors_mod.LoopspecError]
    while stack:
        current = stack.pop()
        for subclass in current.__subclasses__():
            codes.add(subclass.code)
            stack.append(subclass)
    source = Path(errors_mod.__file__).parent
    for path in source.glob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if (
                isinstance(node, ast.Call)
                and getattr(node.func, "id", None) == "WorkflowError"
                and node.args
                and isinstance(node.args[0], ast.Constant)
            ):
                codes.add(node.args[0].value)
    return codes


def external_field_names(model: type[BaseModel]) -> set[str]:
    """Field names as they appear in YAML: alias first, attribute name second."""

    return {
        (info.alias or name)
        for name, info in model.model_fields.items()  # type: ignore[misc]
    }


def marked_examples(lang: str, kind: str) -> list[tuple[Path, CodeBlock]]:
    found: list[tuple[Path, CodeBlock]] = []
    for path in language_pages(lang):
        for block in code_blocks(path.read_text(encoding="utf-8")):
            if block.marker == kind:
                found.append((path, block))
    return found


# --------------------------------------------------------------------------- #
# structure
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("lang", LANGUAGES)
def test_required_pages_exist(lang: str) -> None:
    for relative in REQUIRED_PAGES:
        assert page(lang, relative).is_file(), f"missing docs/{lang}/{relative}"


def test_top_level_has_only_the_language_entry() -> None:
    """docs/ itself carries nothing but the bilingual entry point.

    Dotfiles are excluded: a contributor's `.DS_Store` is not a documentation
    file, and failing on it would say the docs are wrong when they are not.
    """

    top_level = sorted(
        path.name for path in DOCS.iterdir() if path.is_file() and not path.name.startswith(".")
    )
    assert top_level == ["README.md"]


@pytest.mark.parametrize("lang", LANGUAGES)
def test_index_links_every_page(lang: str) -> None:
    index = read(lang, "README.md")
    targets = set(MD_LINK.findall(index))
    for relative in REQUIRED_PAGES:
        if relative == "README.md":
            continue
        assert relative in targets, f"docs/{lang}/README.md does not link {relative}"


@pytest.mark.parametrize("lang", LANGUAGES)
def test_relative_links_resolve(lang: str) -> None:
    for path in language_pages(lang):
        for target in MD_LINK.findall(path.read_text(encoding="utf-8")):
            if target.startswith(("http://", "https://", "mailto:")):
                continue  # never probe the network from a docs test
            anchorless = target.split("#", 1)[0]
            if not anchorless:
                continue
            assert (path.parent / anchorless).exists(), f"{path}: broken link {target}"


@pytest.mark.parametrize("lang", LANGUAGES)
def test_first_screen_declares_scope_audience_and_language(lang: str) -> None:
    other = "zh" if lang == "en" else "en"
    for path in language_pages(lang):
        head = "\n".join(path.read_text(encoding="utf-8").splitlines()[:FIRST_SCREEN_LINES])
        assert "Scope:" in head or "覆盖范围：" in head, f"{path}: no scope line"
        assert "Audience:" in head or "适用读者：" in head, f"{path}: no audience line"
        relative = path.relative_to(DOCS / lang)
        depth = len(relative.parts) - 1
        expected = f"{'../' * (depth + 1)}{other}/{relative.as_posix()}"
        assert expected in head, f"{path}: first screen must link {expected}"


def test_english_pages_do_not_contain_chinese_content() -> None:
    """Only the Chinese-language navigation label may contain Han characters."""
    language_link = re.compile(r"\[中文\]\((?:\.\./)+zh/[^)]+\)")
    han = re.compile("[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\U00020000-\U0002fa1f]")
    for path in language_pages("en"):
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if number <= FIRST_SCREEN_LINES:
                line = language_link.sub("[Chinese]", line)
            assert not han.search(line), f"{path}:{number}: Chinese content in English docs"


@pytest.mark.parametrize("lang", LANGUAGES)
def test_code_blocks_declare_a_language(lang: str) -> None:
    for path in language_pages(lang):
        for block in code_blocks(path.read_text(encoding="utf-8")):
            assert block.language, f"{path}:{block.start_line} fence without a language"


@pytest.mark.parametrize("lang", LANGUAGES)
def test_no_images_no_emoji_and_headings_stay_shallow(lang: str) -> None:
    emoji = re.compile("[\U0001f300-\U0001faff☀-➿]")
    for path in language_pages(lang):
        prose = strip_fenced(path.read_text(encoding="utf-8"))
        for number, line in enumerate(prose.splitlines(), 1):
            assert not re.search(r"!\[[^\]]*\]\(", line), f"{path}: image on prose line {number}"
            assert not emoji.search(line), f"{path}: emoji on prose line {number}"
            heading = re.match(r"^(#+)\s", line)
            if heading:
                assert len(heading.group(1)) <= 3, f"{path}: heading deeper than 3 levels"


@pytest.mark.parametrize("lang", LANGUAGES)
def test_field_tables_use_the_agreed_headers(lang: str) -> None:
    expected = set(FIELD_TABLE_HEADERS[lang])
    other = set(FIELD_TABLE_HEADERS["zh" if lang == "en" else "en"])
    for relative in MODEL_PAGES:
        rows = table_rows(read(lang, relative))
        headers = [set(cells) for cells in rows if len(cells) == 5]
        assert expected in headers, f"docs/{lang}/{relative}: no five-column field table"
        assert other not in headers, f"docs/{lang}/{relative}: uses the other language's headers"


@pytest.mark.parametrize("lang", LANGUAGES)
def test_cross_language_links_only_on_the_first_screen(lang: str) -> None:
    other = "zh" if lang == "en" else "en"
    pattern = re.compile(rf"\]\((?:\.\./)+{other}/")
    for path in language_pages(lang):
        lines = path.read_text(encoding="utf-8").splitlines()
        for number, line in enumerate(lines[FIRST_SCREEN_LINES:], FIRST_SCREEN_LINES + 1):
            assert not pattern.search(line), f"{path}:{number}: cross-language link outside header"


# --------------------------------------------------------------------------- #
# code -> docs coverage, per language
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("lang", LANGUAGES)
def test_every_command_has_a_section(lang: str) -> None:
    sections = command_sections(read(lang, "cli-reference.md"))
    for command in leaf_commands():
        assert command in sections, (
            f"docs/{lang}/cli-reference.md: no `## loopspec {command}` section"
        )


@pytest.mark.parametrize("lang", LANGUAGES)
def test_every_option_is_documented_in_its_own_section(lang: str) -> None:
    sections = command_sections(read(lang, "cli-reference.md"))
    for command, options in leaf_commands().items():
        body = sections.get(command, "")
        for option in options:
            assert f"`{option}`" in body, (
                f"docs/{lang}/cli-reference.md: `{option}` missing from the "
                f"`loopspec {command}` section"
            )


@pytest.mark.parametrize("lang", LANGUAGES)
def test_every_model_field_is_documented(lang: str) -> None:
    for relative, models in MODEL_PAGES.items():
        documented = field_table_names(read(lang, relative))
        for model in models:
            for field in external_field_names(model):
                assert field in documented, (
                    f"docs/{lang}/{relative}: field `{field}` of {model.__name__} "
                    "is not in any field table's first column"
                )


@pytest.mark.parametrize("lang", LANGUAGES)
def test_every_error_code_is_documented(lang: str) -> None:
    documented = first_column_identifiers(read(lang, "cli-reference.md"))
    for code in error_codes():
        assert code in documented, f"docs/{lang}/cli-reference.md: error code `{code}` undocumented"


@pytest.mark.parametrize("lang", LANGUAGES)
def test_documented_defaults_match_the_code(lang: str) -> None:
    cli_text = read(lang, "cli-reference.md")
    config_text = read(lang, "configuration.md")
    composition = read(lang, "workflow-composition.md")

    assert f"`./{cli_mod.DEFAULT_HOME}`" in cli_text, "default workflow home not documented"
    artifacts_default = WorkflowConfig.model_fields["artifacts_dir"].default
    assert f"`{artifacts_default}`" in config_text, "artifacts_dir default not documented"
    retries_default = FailurePolicy.model_fields["max_retries"].default
    assert f"`{retries_default}`" in composition, "max_retries default not documented"


# --------------------------------------------------------------------------- #
# examples really validate
# --------------------------------------------------------------------------- #

EXAMPLE_MODELS: dict[str, type[BaseModel]] = {
    "config": WorkflowConfig,
    "assurance-rules": AssuranceRules,
    "fragment": Fragment,
    "profile": Profile,
    "plan": PlanRequest,
    "plan-file": PlanDocument,
    "change-state": ChangeState,
    "registry-lock": RegistryLock,
}


@pytest.mark.parametrize("lang", LANGUAGES)
def test_marked_examples_validate(lang: str) -> None:
    seen: set[str] = set()
    for path in language_pages(lang):
        for block in code_blocks(path.read_text(encoding="utf-8")):
            if block.marker is None:
                continue
            assert block.marker in EXAMPLE_MODELS, f"{path}: unknown example kind {block.marker}"
            EXAMPLE_MODELS[block.marker].model_validate(yaml.safe_load(block.body))
            seen.add(block.marker)
    assert seen == set(EXAMPLE_MODELS), (
        f"docs/{lang}: missing examples {set(EXAMPLE_MODELS) - seen}"
    )


@pytest.mark.parametrize("lang", LANGUAGES)
def test_plan_file_example_is_a_real_compilation(lang: str, tmp_path: Path) -> None:
    """The documented plan.yaml has a correct digest and is what the compiler produces."""

    import shutil

    home = tmp_path / "home"
    home.mkdir()
    for kind in ("fragments", "profiles"):
        shutil.copytree(builtin_root() / kind, home / kind)
    (home / "config.yaml").write_text("workflow: {}\n", encoding="utf-8")
    for _path, block in marked_examples(lang, "plan-file"):
        document = PlanDocument.model_validate(yaml.safe_load(block.body))
        assert spec_digest(document.spec) == document.meta.digest
        request = PlanRequest(based_on=document.spec.based_on, flow=document.spec.flow)
        assert compile_request(home, request).spec == document.spec


@pytest.mark.parametrize("lang", LANGUAGES)
def test_plan_requests_compile_against_the_builtin_catalog(lang: str, tmp_path: Path) -> None:
    import shutil

    home = tmp_path / "home"
    home.mkdir()
    for kind in ("fragments", "profiles"):
        shutil.copytree(builtin_root() / kind, home / kind)
    (home / "config.yaml").write_text("workflow: {}\n", encoding="utf-8")
    for _path, block in marked_examples(lang, "plan"):
        compile_request(home, PlanRequest.model_validate(yaml.safe_load(block.body)))


@pytest.mark.parametrize("lang", LANGUAGES)
def test_removed_commands_and_fields_are_gone(lang: str) -> None:
    for path in [*language_pages(lang), DOCS.parent / "README.md"]:
        if path.name == "release-notes.md":
            continue
        text = path.read_text(encoding="utf-8")
        for removed in REMOVED_SURFACE:
            assert removed not in text, f"{path}: still mentions {removed!r}"


@pytest.mark.parametrize("lang", LANGUAGES)
def test_examples_carry_no_credentials(lang: str) -> None:
    """Placeholder-only examples.

    Failures name the file, line and rule -- never the matched text, so a real
    secret cannot leak into CI logs through this assertion.
    """

    rules = {
        "home-path": re.compile(r"/(?:Users|home)/(?!<)[A-Za-z0-9._-]+"),
        "bearer-token": re.compile(r"(?i)bearer\s+[A-Za-z0-9._-]{8,}"),
        "api-key-assignment": re.compile(
            r"(?i)\b(?:api[_-]?key|secret|password|token)\b\s*[:=]\s*\S+"
        ),
        "private-host": re.compile(r"\b(?:10|127)\.\d{1,3}\.\d{1,3}\.\d{1,3}\b"),
    }
    for path in language_pages(lang):
        for block in code_blocks(path.read_text(encoding="utf-8")):
            for offset, line in enumerate(block.body.splitlines(), block.start_line + 1):
                for name, rule in rules.items():
                    assert not rule.search(line), f"{path}:{offset}: example matched rule {name}"


# --------------------------------------------------------------------------- #
# language vs language equivalence
# --------------------------------------------------------------------------- #


def test_language_versions_hold_the_same_files() -> None:
    listings = {
        lang: {path.relative_to(DOCS / lang).as_posix() for path in language_pages(lang)}
        for lang in LANGUAGES
    }
    assert listings["en"] == listings["zh"]


def test_command_sections_match_across_languages() -> None:
    titles = {lang: set(command_sections(read(lang, "cli-reference.md"))) for lang in LANGUAGES}
    assert titles["en"] == titles["zh"]


def test_field_names_match_across_languages() -> None:
    for relative in REQUIRED_PAGES:
        names = {lang: first_column_identifiers(read(lang, relative)) for lang in LANGUAGES}
        assert names["en"] == names["zh"], f"{relative}: first-column identifiers differ"


def test_error_codes_match_across_languages() -> None:
    documented = {
        lang: first_column_identifiers(read(lang, "cli-reference.md")) & error_codes()
        for lang in LANGUAGES
    }
    assert documented["en"] == documented["zh"]


LOCALIZED_KEYS = {"description", "guidance", "note", "archive_note"}


def four_layer_example_structure(value: object) -> object:
    """Localize only descriptive fields; identifiers and structure must match."""
    if isinstance(value, dict):
        return {
            key: "<localized text>" if key in LOCALIZED_KEYS else four_layer_example_structure(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [four_layer_example_structure(item) for item in value]
    return value


def test_marked_examples_match_across_languages() -> None:
    """Keep configuration bytes identical and workflow execution structures equal."""

    for relative in REQUIRED_PAGES:
        per_lang = {
            lang: [block for block in code_blocks(read(lang, relative)) if block.marker is not None]
            for lang in LANGUAGES
        }
        assert len(per_lang["en"]) == len(per_lang["zh"]), (
            f"{relative}: {len(per_lang['en'])} marked examples in en, {len(per_lang['zh'])} in zh"
        )
        for index, (left, right) in enumerate(zip(per_lang["en"], per_lang["zh"], strict=True)):
            assert left.marker == right.marker, f"{relative}: example {index} marker differs"
            assert left.language == right.language, f"{relative}: example {index} language differs"
            if left.marker in {"fragment", "profile", "plan", "plan-file"}:
                assert four_layer_example_structure(yaml.safe_load(left.body)) == (
                    four_layer_example_structure(yaml.safe_load(right.body))
                ), f"{relative}: example {index} execution structure differs"
                continue
            if left.body == right.body:
                continue
            left_lines = left.body.splitlines()
            right_lines = right.body.splitlines()
            first_diff = next(
                (
                    number
                    for number, (a, b) in enumerate(zip(left_lines, right_lines, strict=False), 1)
                    if a != b
                ),
                min(len(left_lines), len(right_lines)) + 1,
            )
            pytest.fail(
                f"{relative}: marked example {index} differs between en and zh, "
                f"first difference at example line {first_diff}"
            )
