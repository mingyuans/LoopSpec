import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from loopspec.cli import app
from loopspec.tool_registry import AI_TOOLS

runner = CliRunner()


def run(*args: str) -> tuple[int, dict]:
    result = runner.invoke(app, list(args))
    data = json.loads(result.stdout) if result.stdout.strip() else {}
    return result.exit_code, data


def init_home(tmp_path: Path) -> Path:
    home = tmp_path / "wf"
    code, _ = run("init", str(home), "--json")
    assert code == 0
    return home


def test_version_json():
    code, data = run("version", "--json")
    assert code == 0
    assert "version" in data


def test_version_human_mode():
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert result.stdout.strip()


def test_init_creates_workspace_without_schemas(tmp_path: Path):
    home = init_home(tmp_path)
    assert (home / "config.yaml").read_text() == "artifacts_dir: changes\nworkflow: {}\n"
    assert (home / "changes").is_dir()
    assert (home / "fragments/requirements/fragment.yaml").is_file()
    assert (home / "profiles/bugfix.yaml").is_file()
    assert not (home / "schemas").exists()


def test_init_rejects_removed_no_builtin_flag(tmp_path: Path):
    result = runner.invoke(app, ["init", str(tmp_path / "wf"), "--no-builtin", "--json"])
    assert result.exit_code != 0


def test_init_keeps_existing_resources(tmp_path: Path):
    home = init_home(tmp_path)
    (home / "profiles/bugfix.yaml").write_text("customized")
    code, data = run("init", str(home), "--json")
    assert code == 0
    assert (home / "profiles/bugfix.yaml").read_text() == "customized"
    assert data["copiedWorkflowResources"] == []
    assert data["nextSteps"] == [f"loopspec change new <change-name> --home {home}"]


@pytest.fixture(autouse=True)
def isolated_codex_home(tmp_path: Path, monkeypatch) -> Path:
    """Keep Codex's global prompt scaffolding out of the developer's real ~/.codex.

    `autouse` because `--tools all` now writes 31 tools including Codex, and
    Codex is the one that writes outside the project. Relying on each test to
    remember this fixture would eventually miss one, and the failure mode is
    files appearing in the developer's home directory -- so it is on by default,
    and tests that need the path just request it.
    """

    codex_home = tmp_path / "codex-home"
    monkeypatch.setenv("CODEX_HOME", str(codex_home))
    return codex_home


def test_init_without_tools_flag_scaffolds_nothing(tmp_path: Path):
    project_root = tmp_path / "proj"
    project_root.mkdir()
    code, _ = run("init", str(project_root / "wf"), "--json")
    assert code == 0
    assert not any((project_root / f".{tool}").exists() for tool in ("claude", "codex", "opencode"))


def test_init_scaffolds_into_project_root_not_workflow_home(tmp_path: Path):
    project_root = tmp_path / "proj"
    project_root.mkdir()
    home = project_root / "wf"

    code, data = run("init", str(home), "--tools", "claude", "--json")
    assert code == 0
    assert data["projectRoot"] == str(project_root.resolve())
    # .claude belongs at the project root, where AI tools actually look for it...
    assert (project_root / ".claude" / "skills" / "loopspec-new" / "SKILL.md").is_file()
    assert (project_root / ".claude" / "commands" / "lpsx" / "new.md").is_file()
    # ...and must NOT be buried inside the workflow home.
    assert not (home / ".claude").exists()


def test_init_project_root_override(tmp_path: Path):
    home = tmp_path / "wf"
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()

    code, data = run(
        "init", str(home), "--tools", "claude", "--project-root", str(elsewhere), "--json"
    )
    assert code == 0
    assert data["projectRoot"] == str(elsewhere.resolve())
    assert (elsewhere / ".claude" / "skills" / "loopspec-new" / "SKILL.md").is_file()
    assert not (tmp_path / ".claude").exists()


def test_init_tools_all_scaffolds_every_registered_tool(tmp_path: Path, isolated_codex_home: Path):
    project_root = tmp_path / "proj"
    project_root.mkdir()

    code, data = run("init", str(project_root / "wf"), "--tools", "all", "--json")
    assert code == 0
    assert set(data["toolsConfigured"]) == set(AI_TOOLS)
    assert (project_root / ".claude" / "skills" / "loopspec-new" / "SKILL.md").is_file()
    assert (project_root / ".claude" / "commands" / "lpsx" / "new.md").is_file()
    assert (project_root / ".opencode" / "commands" / "lpsx-new.md").is_file()
    # Codex commands are user-global by design, not project-local.
    assert (isolated_codex_home / "prompts" / "lpsx-new.md").is_file()
    assert not (project_root / ".codex" / "commands").exists()


def test_init_tools_subset(tmp_path: Path, isolated_codex_home: Path):
    project_root = tmp_path / "proj"
    project_root.mkdir()

    code, data = run("init", str(project_root / "wf"), "--tools", "claude,codex", "--json")
    assert code == 0
    assert set(data["toolsConfigured"]) == {"claude", "codex"}
    assert (project_root / ".claude" / "skills" / "loopspec-archive" / "SKILL.md").is_file()
    assert not (project_root / ".opencode").exists()


def test_init_tools_unknown_id_rejected(tmp_path: Path):
    home = tmp_path / "wf"
    code, data = run("init", str(home), "--tools", "not-a-real-tool", "--json")
    assert code == 1
    assert data["error"] == "config_invalid"
    assert "claude" in data["fix"]


ANSI_ESCAPE = "\x1b["


def human_init(*args: str) -> str:
    """Run `init` without --json and return its human-readable stdout."""

    result = runner.invoke(app, list(args))
    assert result.exit_code == 0, result.stdout
    return result.stdout


def test_init_json_stdout_parses_whole_and_carries_no_decoration(tmp_path: Path):
    result = runner.invoke(app, ["init", str(tmp_path / "wf"), "--tools", "claude", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)  # whole stdout, not a fragment
    assert payload["toolsConfigured"] == ["claude"]
    assert ANSI_ESCAPE not in result.stdout
    for marker in ("Setup complete", "Workflow home ready", "LoopSpec Setup Complete", "✔", "▌"):
        assert marker not in result.stdout


def test_init_human_output_leaks_no_json_field_names_or_python_reprs(tmp_path: Path):
    output = human_init("init", str(tmp_path / "wf"), "--tools", "claude")
    for field in (
        "scaffoldedFiles",
        "skippedCommandGeneration",
        "toolsConfigured",
        "workflowHome",
        "copiedWorkflowResources",
        "createdFiles",
        "nextSteps",
    ):
        assert field not in output
    assert "{'" not in output and "['" not in output


def test_init_human_output_summarizes_instead_of_listing_paths(tmp_path: Path):
    output = human_init("init", str(tmp_path / "wf"), "--tools", "claude")
    assert "4 skills and 4 commands in .claude" in output
    assert "SKILL.md" not in output
    assert "commands/lpsx" not in output


def test_init_human_output_has_created_then_refreshed(tmp_path: Path):
    home = tmp_path / "proj" / "wf"
    first = human_init("init", str(home), "--tools", "claude")
    assert "Created: Claude Code" in first
    assert "Refreshed:" not in first

    second = human_init("init", str(home), "--tools", "claude")
    assert "Refreshed: Claude Code" in second
    assert "Created:" not in second


def test_init_human_output_config_created_then_exists(tmp_path: Path):
    home = tmp_path / "wf"
    first = human_init("init", str(home), "--tools", "none")
    assert "(created)" in first
    assert "schema" not in first.lower()

    second = human_init("init", str(home), "--tools", "none")
    assert "(exists)" in second


def test_init_human_output_ends_with_getting_started_and_links(tmp_path: Path):
    output = human_init("init", str(tmp_path / "wf"), "--tools", "claude")
    assert "Getting started:" in output
    assert "https://github.com/mingyuans/LoopSpec" in output
    assert "https://github.com/mingyuans/LoopSpec/issues" in output
    assert "Restart your IDE for slash commands to take effect." in output


def test_init_human_output_without_tools_omits_restart_hint(tmp_path: Path):
    output = human_init("init", str(tmp_path / "wf"), "--tools", "none")
    assert "Restart your IDE" not in output
    assert "skills and" not in output


def test_init_human_output_renders_markup_like_paths_verbatim(tmp_path: Path):
    project_root = tmp_path / "[red]proj"
    project_root.mkdir()
    output = human_init("init", str(project_root / "wf"), "--tools", "claude")
    # The path must appear as typed; rich markup parsing would have eaten `[red]`.
    assert "[red]proj" in output


def test_aggregated_path_details_remain_available_via_json(tmp_path: Path):
    home = tmp_path / "proj" / "wf"
    human_init("init", str(home), "--tools", "claude")

    code, data = run("init", str(home), "--tools", "claude", "--json")
    assert code == 0
    claude_files = data["scaffoldedFiles"]["claude"]
    assert len(claude_files) == 8
    assert any(path.endswith("loopspec-new/SKILL.md") for path in claude_files)
    assert data["refreshedTools"] == ["claude"]


def test_init_tools_rerun_overwrites_existing_scaffold(tmp_path: Path):
    project_root = tmp_path / "proj"
    project_root.mkdir()
    home = project_root / "wf"

    run("init", str(home), "--tools", "claude", "--json")
    skill_file = project_root / ".claude" / "skills" / "loopspec-new" / "SKILL.md"
    skill_file.write_text("hand-edited")

    code, _ = run("init", str(home), "--tools", "claude", "--json")
    assert code == 0
    assert "hand-edited" not in skill_file.read_text()


# --------------------------------------------------------------------------- #
# welcome screen / picker: the three non-interactive paths (tasks 6.1-6.3)
#
# The picker's dependency on a real terminal is exactly why these matter: if the
# gate leaks, CI and piped output start failing on a missing tty.
# --------------------------------------------------------------------------- #

WELCOME_MARKERS = (
    "Welcome to LoopSpec",
    "This setup will configure:",
    "Quick start after setup:",
    "Press Enter to select tools",
    "█",
)

PICKER_MARKERS = ("Select tools to set up", "navigate", "Space toggle")


def assert_no_interaction(output: str) -> None:
    for marker in WELCOME_MARKERS + PICKER_MARKERS:
        assert marker not in output, marker


def test_json_mode_carries_no_welcome_screen_or_picker(tmp_path: Path):
    result = runner.invoke(app, ["init", str(tmp_path / "wf"), "--tools", "claude", "--json"])
    assert result.exit_code == 0
    json.loads(result.stdout)  # still parses as a whole
    assert ANSI_ESCAPE not in result.stdout
    assert_no_interaction(result.stdout)


def test_json_mode_skips_interaction_even_with_a_terminal(tmp_path: Path, monkeypatch):
    """`--json` wins over an available tty -- the JSON protocol must never carry
    a prompt, and questionary would render one straight to the terminal."""

    monkeypatch.setattr("loopspec.cli.is_interactive", lambda: True)
    monkeypatch.setattr(
        "loopspec.cli.pick_tools", lambda *a, **k: pytest.fail("picker ran on the JSON path")
    )

    result = runner.invoke(app, ["init", str(tmp_path / "wf"), "--json"])
    assert result.exit_code == 0
    assert json.loads(result.stdout)["toolsConfigured"] == []


def test_explicit_tools_skips_the_welcome_screen(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("loopspec.cli.is_interactive", lambda: True)
    monkeypatch.setattr(
        "loopspec.cli.pick_tools", lambda *a, **k: pytest.fail("picker ran despite --tools")
    )

    output = human_init("init", str(tmp_path / "wf"), "--tools", "claude")
    assert_no_interaction(output)
    assert "Created: Claude Code" in output


@pytest.mark.parametrize("tools_arg", [["--tools", "all"], ["--tools", "none"]])
def test_tools_all_and_none_also_skip_the_picker(
    tmp_path: Path, monkeypatch, isolated_codex_home: Path, tools_arg: list[str]
):
    monkeypatch.setattr("loopspec.cli.is_interactive", lambda: True)
    monkeypatch.setattr(
        "loopspec.cli.pick_tools", lambda *a, **k: pytest.fail("picker ran despite an explicit arg")
    )

    output = human_init("init", str(tmp_path / "proj" / "wf"), *tools_arg)
    assert_no_interaction(output)


def test_non_interactive_without_tools_renders_nothing_and_succeeds(tmp_path: Path):
    """Equivalent to `--tools none`: no welcome screen, no picker, no scaffolding,
    and no error -- the behaviour redirected output and CI have always had."""

    project_root = tmp_path / "proj"
    project_root.mkdir()

    output = human_init("init", str(project_root / "wf"))

    assert_no_interaction(output)
    assert not (project_root / ".claude").exists()
    assert "Config:" in output  # the rest of init still ran


def test_interactive_path_renders_welcome_and_runs_picker_together(tmp_path: Path, monkeypatch):
    """design D3: one condition drives both, so neither appears without the other."""

    monkeypatch.setattr("loopspec.cli.is_interactive", lambda: True)
    calls: list[str] = []
    monkeypatch.setattr("loopspec.cli.pick_tools", lambda *a, **k: calls.append("picked") or [])

    result = runner.invoke(app, ["init", str(tmp_path / "proj" / "wf")], input="\n")

    assert result.exit_code == 0, result.stdout
    assert calls == ["picked"], "the welcome screen promised a picker"
    for marker in WELCOME_MARKERS:
        assert marker in result.stdout, marker


# --------------------------------------------------------------------------- #
# artifacts
# --------------------------------------------------------------------------- #
