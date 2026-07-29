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


def make_multi_schema_home(tmp_path: Path) -> Path:
    home = tmp_path / "wf"
    code, _ = run("init", str(home), "--no-builtin", "--json")
    assert code == 0
    for name in ("secure-spec-driven", "docs-only"):
        schema_dir = home / "schemas" / name
        schema_dir.mkdir(parents=True)
        templates_dir = schema_dir / "templates"
        templates_dir.mkdir()
        (templates_dir / "proposal.md").write_text("# proposal template")
        (schema_dir / "schema.yaml").write_text(
            f"""
name: {name}
version: 1
nodes:
  - id: proposal
    generates: proposal.md
    description: proposal
    template: proposal.md
    requires: []
    instruction: "write it"
"""
        )
    (home / "config.yaml").write_text(
        """
schemas:
  - name: secure-spec-driven
    description: default
    when: general
  - name: docs-only
    description: docs
    when: docs only
schema_selection:
  instruction: pick the best match
"""
    )
    return home


def write_planning_artifacts(change_dir: Path, tasks_body: str = "- [x] 1.1 ship it\n") -> None:
    """Fake the built-in schema's planning artifacts through the security gate."""

    (change_dir / "proposal.md").write_text("# p")
    (change_dir / "design.md").write_text("# d")
    (change_dir / "specs").mkdir(exist_ok=True)
    (change_dir / "specs" / "spec.md").write_text("# s")
    (change_dir / "tasks.md").write_text(tasks_body)
    (change_dir / "security").mkdir(exist_ok=True)
    (change_dir / "security" / "pass.md").write_text("# ok")


def complete_builtin_change(change_dir: Path, tasks_body: str = "- [x] 1.1 ship it\n") -> None:
    """Everything the built-in schema needs to reach `isComplete`, approval and apply included."""

    write_planning_artifacts(change_dir, tasks_body)
    (change_dir / "approval").mkdir(exist_ok=True)
    (change_dir / "approval" / "approved.md").write_text("# Human Approval: APPROVED")
    (change_dir / "apply").mkdir(exist_ok=True)
    (change_dir / "apply" / "report.md").write_text("# Implementation Report")


def test_version_json():
    code, data = run("version", "--json")
    assert code == 0
    assert "version" in data


def test_version_human_mode():
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert result.stdout.strip()


def test_init_copies_builtin_schema(tmp_path: Path):
    home = init_home(tmp_path)
    assert (home / "schemas" / "secure-spec-driven" / "schema.yaml").is_file()
    assert (home / "config.yaml").is_file()
    assert (home / "changes").is_dir()


def test_init_no_builtin_skips_schema(tmp_path: Path):
    home = tmp_path / "wf"
    code, _ = run("init", str(home), "--no-builtin", "--json")
    assert code == 0
    assert not any((home / "schemas").iterdir())


def test_schemas_list_and_validate(tmp_path: Path):
    home = init_home(tmp_path)
    code, data = run("schemas", "list", "--home", str(home), "--json")
    assert code == 0
    assert data["schemas"][0]["name"] == "secure-spec-driven"

    code, data = run("schemas", "validate", "secure-spec-driven", "--home", str(home), "--json")
    assert code == 0
    assert data["valid"] is True
    assert data["buildOrder"][0] == "proposal"


def test_new_creates_change(tmp_path: Path):
    home = init_home(tmp_path)
    code, data = run("new", "add-payment", "--home", str(home), "--json")
    assert code == 0
    assert data["schemaName"] == "secure-spec-driven"
    change_dir = Path(data["changeRoot"])
    assert (change_dir / ".workflow.yaml").is_file()
    assert (change_dir / "state.md").is_file()


def test_new_invalid_name_rejected(tmp_path: Path):
    home = init_home(tmp_path)
    code, data = run("new", "Not_Valid", "--home", str(home), "--json")
    assert code == 1
    assert data["error"] == "invalid_change_name"


def test_new_duplicate_rejected(tmp_path: Path):
    home = init_home(tmp_path)
    run("new", "add-payment", "--home", str(home), "--json")
    code, data = run("new", "add-payment", "--home", str(home), "--json")
    assert code == 1
    assert data["error"] == "change_exists"


def test_new_multi_schema_requires_selection(tmp_path: Path):
    home = make_multi_schema_home(tmp_path)
    code, data = run("new", "add-payment", "--home", str(home), "--json")
    assert code == 1
    assert data["error"] == "schema_selection_required"
    assert {s["name"] for s in data["schemas"]} == {"secure-spec-driven", "docs-only"}
    assert data["selectionInstruction"] == "pick the best match"

    code, data = run(
        "new", "add-payment", "--schema", "docs-only", "--home", str(home), "--json"
    )
    assert code == 0
    assert data["schemaName"] == "docs-only"


def test_status_reflects_ready_node(tmp_path: Path):
    home = init_home(tmp_path)
    run("new", "add-payment", "--home", str(home), "--json")
    code, data = run("status", "add-payment", "--home", str(home), "--json")
    assert code == 0
    assert data["nodes"][0]["status"] == "ready"
    assert "instructions proposal" in data["nextSteps"][0]


TRACKING_SCHEMA_YAML = """
name: tracked
version: 1
nodes:
  - id: tasks
    generates: tasks.md
    description: tasks
    template: tasks.md
    requires: []
    instruction: "write the tasks"
  - id: apply
    generates: null
    description: implementation
    template: null
    requires: [tasks]
    tracks: tasks.md
    instruction: "implement it"
    gate:
      outputs:
        pass: apply/report.md
        fail: apply/blocked.md
      templates:
        pass: apply-report.md
        fail: apply-blocked.md
      on_fail:
        reset: [tasks]
"""


def make_tracking_home(tmp_path: Path) -> Path:
    home = tmp_path / "wf"
    code, _ = run("init", str(home), "--no-builtin", "--json")
    assert code == 0
    schema_dir = home / "schemas" / "tracked"
    templates_dir = schema_dir / "templates"
    templates_dir.mkdir(parents=True)
    for name in ("tasks.md", "apply-report.md", "apply-blocked.md"):
        (templates_dir / name).write_text(f"# {name}")
    (schema_dir / "schema.yaml").write_text(TRACKING_SCHEMA_YAML)
    (home / "config.yaml").write_text("artifacts_dir: changes\nschema: tracked\n")
    return home


def test_status_reports_task_progress_for_tracked_node(tmp_path: Path):
    home = make_tracking_home(tmp_path)
    code, data = run("new", "add-payment", "--home", str(home), "--json")
    assert code == 0
    change_dir = Path(data["changeRoot"])
    (change_dir / "tasks.md").write_text("- [x] 1.1 done\n- [ ] 1.2 pending\n- [ ] 1.3 pending\n")

    code, data = run("status", "add-payment", "--home", str(home), "--json")
    assert code == 0
    apply_node = next(node for node in data["nodes"] if node["id"] == "apply")
    assert apply_node["taskProgress"]["path"] == "tasks.md"
    assert apply_node["taskProgress"]["total"] == 3
    assert apply_node["taskProgress"]["complete"] == 1
    assert apply_node["taskProgress"]["remaining"] == 2
    # Per-task detail belongs to `instructions`, not to the hot-path `status` call.
    assert "tasks" not in apply_node["taskProgress"]

    tasks_node = next(node for node in data["nodes"] if node["id"] == "tasks")
    assert "taskProgress" not in tasks_node


def test_status_tracked_node_stays_ready_until_every_task_ticked(tmp_path: Path):
    home = make_tracking_home(tmp_path)
    code, data = run("new", "add-payment", "--home", str(home), "--json")
    change_dir = Path(data["changeRoot"])
    (change_dir / "tasks.md").write_text("- [x] 1.1 done\n- [ ] 1.2 pending\n")
    (change_dir / "apply").mkdir()
    (change_dir / "apply" / "report.md").write_text("# Implementation report")

    code, data = run("status", "add-payment", "--home", str(home), "--json")
    apply_node = next(node for node in data["nodes"] if node["id"] == "apply")
    assert apply_node["status"] == "ready"
    assert data["isComplete"] is False

    code, data = run("archive", "add-payment", "--home", str(home), "--json")
    assert code == 1
    assert data["error"] == "archive_unsafe"

    (change_dir / "tasks.md").write_text("- [x] 1.1 done\n- [x] 1.2 done\n")
    code, data = run("status", "add-payment", "--home", str(home), "--json")
    assert data["isComplete"] is True


def test_status_change_not_found(tmp_path: Path):
    home = init_home(tmp_path)
    code, data = run("status", "nonexistent", "--home", str(home), "--json")
    assert code == 1
    assert data["error"] == "change_not_found"


def test_instructions_returns_template(tmp_path: Path):
    home = init_home(tmp_path)
    run("new", "add-payment", "--home", str(home), "--json")
    code, data = run(
        "instructions", "proposal", "--change", "add-payment", "--home", str(home), "--json"
    )
    assert code == 0
    assert "Why" in data["template"]
    assert data["priorAttempts"] == []


def test_full_lifecycle_with_rollback_and_completion(tmp_path: Path):
    home = init_home(tmp_path)
    code, data = run("new", "add-payment", "--home", str(home), "--json")
    assert code == 0
    change_dir = Path(data["changeRoot"])

    (change_dir / "proposal.md").write_text("# proposal")
    (change_dir / "design.md").write_text("# design")
    (change_dir / "specs").mkdir()
    (change_dir / "specs" / "spec.md").write_text("# spec")
    (change_dir / "tasks.md").write_text("- [ ] 1.1 build it")
    (change_dir / "security").mkdir()
    (change_dir / "security" / "fail.md").write_text("# Blocked\n\n- injection risk")

    code, data = run("status", "add-payment", "--home", str(home), "--json")
    assert code == 0
    assert data["pendingRollback"]["gate"] == "security"

    code, data = run("rollback", "add-payment", "--home", str(home), "--json")
    assert code == 0
    assert data["round"] == 1
    assert not (change_dir / "design.md").exists()

    code, data = run(
        "instructions", "design", "--change", "add-payment", "--home", str(home), "--json"
    )
    assert code == 0
    assert len(data["priorAttempts"]) == 1
    assert data["priorAttempts"][0]["blockingIssues"] == ["injection risk"]

    (change_dir / "design.md").write_text("# design v2")
    (change_dir / "tasks.md").write_text("- [x] 1.1 build it")
    (change_dir / "security").mkdir(exist_ok=True)
    (change_dir / "security" / "pass.md").write_text("# ok")

    # Security PASS only unlocks human approval; implementation is still gated.
    code, data = run("status", "add-payment", "--home", str(home), "--json")
    assert code == 0
    assert data["isComplete"] is False
    statuses = {node["id"]: node["status"] for node in data["nodes"]}
    assert statuses["approval"] == "ready"
    assert statuses["apply"] == "blocked"

    (change_dir / "approval").mkdir()
    (change_dir / "approval" / "approved.md").write_text("# Human Approval: APPROVED")
    (change_dir / "apply").mkdir()
    (change_dir / "apply" / "report.md").write_text("# Implementation Report")

    code, data = run("status", "add-payment", "--home", str(home), "--json")
    assert code == 0
    assert data["isComplete"] is True

    code, data = run("history", "add-payment", "--home", str(home), "--json")
    assert code == 0
    assert len(data["rounds"]) == 1
    assert data["rounds"][0]["gate"] == "security"


def test_rollback_no_failed_gate(tmp_path: Path):
    home = init_home(tmp_path)
    run("new", "add-payment", "--home", str(home), "--json")
    code, data = run("rollback", "add-payment", "--home", str(home), "--json")
    assert code == 1
    assert data["error"] == "no_failed_gate"


def test_archive_unsafe_when_incomplete(tmp_path: Path):
    home = init_home(tmp_path)
    run("new", "add-payment", "--home", str(home), "--json")
    code, data = run("archive", "add-payment", "--home", str(home), "--json")
    assert code == 1
    assert data["error"] == "archive_unsafe"


def test_archive_dry_run_then_apply(tmp_path: Path):
    home = init_home(tmp_path)
    code, data = run("new", "add-payment", "--home", str(home), "--json")
    change_dir = Path(data["changeRoot"])
    complete_builtin_change(change_dir)

    code, data = run("archive", "add-payment", "--dry-run", "--home", str(home), "--json")
    assert code == 0
    assert data["dryRun"] is True
    assert change_dir.exists()

    code, data = run("archive", "add-payment", "--home", str(home), "--json")
    assert code == 0
    assert data["moved"] is True
    assert not change_dir.exists()
    assert Path(data["destination"]).exists()


def test_archive_conflict(tmp_path: Path):
    home = init_home(tmp_path)
    code, data = run("new", "add-payment", "--home", str(home), "--json")
    complete_builtin_change(Path(data["changeRoot"]))

    run("archive", "add-payment", "--home", str(home), "--json")

    code, data = run("new", "add-payment", "--home", str(home), "--json")
    complete_builtin_change(Path(data["changeRoot"]))

    code, data = run("archive", "add-payment", "--home", str(home), "--json")
    assert code == 1
    assert data["error"] == "archive_conflict"


def test_bulk_archive_dry_run_lists_candidates(tmp_path: Path):
    home = init_home(tmp_path)
    code, data = run("new", "add-payment", "--home", str(home), "--json")
    change_dir = Path(data["changeRoot"])
    complete_builtin_change(change_dir)

    code, data = run("bulk-archive", "--dry-run", "--home", str(home), "--json")
    assert code == 0
    assert data["dryRun"] is True
    assert len(data["candidates"]) == 1
    assert change_dir.exists()


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
    assert not any(
        (project_root / f".{tool}").exists() for tool in ("claude", "codex", "opencode")
    )


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
        "copiedSchemas",
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
    assert "(schema: secure-spec-driven)" in first

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
    output = human_init(
        "init", str(project_root / "wf"), "--tools", "claude"
    )
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
