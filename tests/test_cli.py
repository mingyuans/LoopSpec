import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from loopspec.cli import app

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
    (change_dir / "tasks.md").write_text("# tasks")
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
    (change_dir / "tasks.md").write_text("# tasks v2")
    (change_dir / "security").mkdir(exist_ok=True)
    (change_dir / "security" / "pass.md").write_text("# ok")

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
    (change_dir / "proposal.md").write_text("# p")
    (change_dir / "design.md").write_text("# d")
    (change_dir / "specs").mkdir()
    (change_dir / "specs" / "spec.md").write_text("# s")
    (change_dir / "tasks.md").write_text("# t")
    (change_dir / "security").mkdir()
    (change_dir / "security" / "pass.md").write_text("# ok")

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
    change_dir = Path(data["changeRoot"])
    for name, content in (
        ("proposal.md", "# p"),
        ("design.md", "# d"),
        ("tasks.md", "# t"),
    ):
        (change_dir / name).write_text(content)
    (change_dir / "specs").mkdir()
    (change_dir / "specs" / "spec.md").write_text("# s")
    (change_dir / "security").mkdir()
    (change_dir / "security" / "pass.md").write_text("# ok")

    run("archive", "add-payment", "--home", str(home), "--json")

    code, data = run("new", "add-payment", "--home", str(home), "--json")
    change_dir2 = Path(data["changeRoot"])
    for name, content in (
        ("proposal.md", "# p"),
        ("design.md", "# d"),
        ("tasks.md", "# t"),
    ):
        (change_dir2 / name).write_text(content)
    (change_dir2 / "specs").mkdir()
    (change_dir2 / "specs" / "spec.md").write_text("# s")
    (change_dir2 / "security").mkdir()
    (change_dir2 / "security" / "pass.md").write_text("# ok")

    code, data = run("archive", "add-payment", "--home", str(home), "--json")
    assert code == 1
    assert data["error"] == "archive_conflict"


def test_bulk_archive_dry_run_lists_candidates(tmp_path: Path):
    home = init_home(tmp_path)
    code, data = run("new", "add-payment", "--home", str(home), "--json")
    change_dir = Path(data["changeRoot"])
    (change_dir / "proposal.md").write_text("# p")
    (change_dir / "design.md").write_text("# d")
    (change_dir / "specs").mkdir()
    (change_dir / "specs" / "spec.md").write_text("# s")
    (change_dir / "tasks.md").write_text("# t")
    (change_dir / "security").mkdir()
    (change_dir / "security" / "pass.md").write_text("# ok")

    code, data = run("bulk-archive", "--dry-run", "--home", str(home), "--json")
    assert code == 0
    assert data["dryRun"] is True
    assert len(data["candidates"]) == 1
    assert change_dir.exists()


@pytest.fixture
def isolated_codex_home(tmp_path: Path, monkeypatch) -> Path:
    """Keep Codex's global prompt scaffolding out of the developer's real ~/.codex."""

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
    assert set(data["toolsConfigured"]) == {"claude", "codex", "opencode", "cursor", "windsurf"}
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
