"""The `loopspec <resource> <verb>` command tree, JSON output and Change archive (T1–T5, T7)."""

import json
from datetime import date
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from loopspec.cli import app
from tests.workflow_helpers import (
    CHANGE,
    DOCS_FLOW,
    archive_change,
    create_approved,
    create_draft,
    fail_gate,
    home_fixture,
    invoke,
    new_change,
    pass_node,
    project,
    status,
)

runner = CliRunner()
QA_FLOW = [
    {"id": "requirements", "use": "requirements"},
    {
        "id": "qa",
        "use": "qa-testing",
        "requires": ["requirements"],
        "on_fail": {"reset": ["requirements"], "max_retries": 2},
    },
]
TREE = {
    "change": {"new", "status", "next", "history", "artifacts", "archive"},
    "plan": {"validate", "create", "show", "list", "approve", "archive", "rollback"},
    "node": {"instructions"},
    "gate": {"begin", "record"},
    "state": {"add"},
    "fragment": {"list", "show", "validate"},
    "profile": {"list", "show", "validate", "save"},
    "registry": {"update", "apply"},
    "hook": {"pre-tool-use"},
    "memory": {"list", "show"},
}


def commands(group=None) -> set[str]:
    import typer.main

    command = typer.main.get_command(app)
    if group:
        command = command.commands[group]  # type: ignore[attr-defined]
    return set(command.commands)  # type: ignore[attr-defined]


def test_top_level_commands_are_resources():
    assert commands() == {"version", "update", "init", "graph", *TREE}
    for group, verbs in TREE.items():
        assert commands(group) == verbs


@pytest.mark.parametrize(
    "args",
    [
        ["schemas", "list"],
        ["assurance", "check", CHANGE],
        ["recover", CHANGE],
        ["new", CHANGE],
        ["status", CHANGE],
        ["next", CHANGE],
        ["instructions", "x", "--change", CHANGE],
        ["rollback", CHANGE],
        ["history", CHANGE],
        ["artifacts", CHANGE],
        ["archive", CHANGE],
        ["bulk-archive"],
        ["plans", "list"],
        ["fragments", "list"],
        ["profiles", "list"],
    ],
)
def test_removed_commands_do_not_exist(tmp_path: Path, args):
    result = runner.invoke(app, [*args, "--home", str(tmp_path)])
    assert result.exit_code == 2


@pytest.mark.parametrize(
    "flag", ["--message", "--expected-digest", "--reason", "--safety-expansion"]
)
def test_removed_flags_do_not_exist(tmp_path: Path, flag):
    home = home_fixture(tmp_path)
    result = runner.invoke(
        app,
        [
            "plan",
            "approve",
            "-c",
            CHANGE,
            "-p",
            "001",
            "--digest",
            "x",
            flag,
            "y",
            "--home",
            str(home),
        ],
    )
    assert result.exit_code == 2


def test_workflow_commands_print_text_unless_asked_for_json(tmp_path: Path):
    home = home_fixture(tmp_path)
    result = runner.invoke(app, ["change", "new", CHANGE, "--home", str(home)])
    assert result.exit_code == 0 and result.stdout.startswith("=== CHANGE ===\n")
    assert f"changeName:   {CHANGE}" in result.stdout
    result = runner.invoke(app, ["change", "new", CHANGE, "--json", "--home", str(home)])
    assert result.exit_code == 0 and json.loads(result.stdout)["changeName"] == CHANGE
    result = runner.invoke(app, ["change", "status", "missing", "--json", "--home", str(home)])
    assert result.exit_code == 1
    assert set(json.loads(result.stdout)) == {"error", "message", "fix"}
    result = runner.invoke(app, ["change", "status", CHANGE, "--home", str(home)])
    assert result.exit_code == 0 and result.stdout.startswith("=== OVERVIEW ===\n")


def test_catalog_commands(tmp_path: Path):
    home = home_fixture(tmp_path)
    fragments = invoke(home, "fragment", "list")[1]["fragments"]
    assert "requirements" in {item["name"] for item in fragments}
    assert invoke(home, "fragment", "show", "requirements")[1]["name"] == "requirements"
    assert invoke(home, "fragment", "validate", "backend-implementation")[1]["valid"]
    profiles = invoke(home, "profile", "list")[1]["profiles"]
    assert {item["name"] for item in profiles} == {
        "bugfix",
        "frontend-small-change",
        "large-feature",
    }
    assert "protected" not in json.dumps(profiles)
    assert invoke(home, "profile", "show", "bugfix")[1]["flow"]
    assert invoke(home, "profile", "validate", "bugfix")[1]["valid"]


def test_fragment_validate_rejects_removed_fields(tmp_path: Path):
    home = home_fixture(tmp_path)
    path = home / "fragments/requirements/fragment.yaml"
    path.write_text(path.read_text() + "min_engine_version: 2\n")
    code, result = invoke(home, "fragment", "validate", "requirements")
    assert code == 1 and result["error"] == "workflow_invalid"


def test_profile_save_keeps_flow_on_fail_and_never_overwrites(tmp_path: Path):
    home = project(tmp_path, code=False)
    create_approved(home, QA_FLOW)
    code, result = invoke(home, "profile", "save", "my-flow", "-c", CHANGE)
    assert code == 0 and result["includesRuntimeState"] is False
    saved = yaml.safe_load((home / "profiles/my-flow.yaml").read_text())
    assert saved["flow"][1]["on_fail"] == {"reset": ["requirements"], "max_retries": 2}
    assert not {"protected", "min_engine_version", "meta", "nodes"} & set(saved)
    code, result = invoke(home, "profile", "save", "my-flow", "-c", CHANGE)
    assert code == 1 and result["error"] == "profile_exists"


def test_history_lists_rework_records_per_plan(tmp_path: Path):
    home = project(tmp_path, code=False)
    create_approved(home, QA_FLOW)
    pass_node(home, "requirements/proposal")
    fail_gate(home, "qa/test")
    assert invoke(home, "plan", "rollback", "-c", CHANGE, "-p", "001")[0] == 0
    history = invoke(home, "change", "history", CHANGE)[1]
    assert history["plan"] == "001"
    [record] = history["attempts"]
    assert record["kind"] == "rollback" and record["gate"] == "qa/test"
    invoke(home, "plan", "archive", "-c", CHANGE, "-p", "001")
    create_draft(home, QA_FLOW)
    assert invoke(home, "change", "history", CHANGE)[1]["attempts"] == []
    assert len(invoke(home, "change", "history", CHANGE, "-p", "001")[1]["attempts"]) == 1


def test_artifacts_are_grouped_by_plan_including_archived(tmp_path: Path):
    home = project(tmp_path, code=False)
    create_approved(home, DOCS_FLOW)
    pass_node(home, "requirements/proposal")
    invoke(home, "plan", "archive", "-c", CHANGE, "-p", "001")
    from tests.workflow_helpers import approve

    approve(home, create_draft(home, DOCS_FLOW)["plan"])
    for identity in ("requirements/proposal", "design/design", "design/tasks"):
        pass_node(home, identity)
    assert archive_change(home)[0] == 0
    result = invoke(home, "change", "artifacts", CHANGE)[1]
    [location] = result["locations"]
    assert location["location"] == f"archive/{date.today():%Y-%m}"
    by_plan = {item["plan"]: item for item in location["plans"]}
    assert by_plan["001"]["status"] == "archived" and len(by_plan["001"]["artifacts"]) == 1
    assert len(by_plan["002"]["artifacts"]) == 3


def test_archive_refuses_unfinished_change_unless_forced(tmp_path: Path):
    home = project(tmp_path, code=False)
    create_approved(home, DOCS_FLOW)
    code, result = invoke(home, "change", "archive", CHANGE)
    assert code == 1 and result["error"] == "archive_unsafe"
    code, result = invoke(home, "change", "archive", CHANGE, "--force")
    [change] = result["changes"]
    assert code == 0 and change["forced"] and "未完成" in change["message"]
    assert (home / "changes" / CHANGE).is_dir()
    code, result = archive_change(home, CHANGE, "--force")
    assert code == 0 and result["archived"][0]["moved"] and result["archived"][0]["forced"]
    assert not (home / "changes" / CHANGE).exists()


def test_archive_complete_change(tmp_path: Path):
    home = project(tmp_path, code=False)
    create_approved(home, DOCS_FLOW)
    for identity in ("requirements/proposal", "design/design", "design/tasks"):
        pass_node(home, identity)
    assert status(home)["status"] == "complete"
    code, result = invoke(home, "change", "archive", CHANGE)
    assert code == 0 and result["changes"][0]["complete"] and not result["changes"][0]["forced"]
    assert (home / "changes" / CHANGE).is_dir()  # the first step archives nothing
    assert archive_change(home)[1]["archived"][0]["moved"]
    assert (home / f"archive/{date.today():%Y-%m}" / CHANGE / ".workflow.yaml").is_file()


def test_archive_all_only_takes_complete_changes(tmp_path: Path):
    home = project(tmp_path, code=False)
    create_approved(home, DOCS_FLOW)
    for identity in ("requirements/proposal", "design/design", "design/tasks"):
        pass_node(home, identity)
    new_change(home, "OTHER1")
    code, result = invoke(home, "change", "archive", "--all")
    assert code == 0
    assert [item["changeName"] for item in result["changes"]] == [CHANGE]
    assert result["skipped"] == [{"changeName": "OTHER1", "reason": "archive_unsafe"}]
    code, result = invoke(home, "change", "archive", "--all", "--older-than", "1")
    assert code == 0 and result["changes"] == [] and result["archiveId"] is None
    assert {item["reason"] for item in result["skipped"]} == {"too_recent"}
    code, result = archive_change(home, "--all")
    assert [item["changeName"] for item in result["archived"]] == [CHANGE]


@pytest.mark.parametrize(
    "args",
    [
        ["change", "archive"],
        ["change", "archive", CHANGE, "--all"],
        ["change", "archive", "--all", "--force"],
        ["change", "archive", CHANGE, "--older-than", "3"],
        ["change", "archive", CHANGE, "--confirm", "0" * 64, "--memory", "none", "--note", "x"],
        ["change", "archive", "--all", "--confirm", "0" * 64, "--memory", "none", "--note", "x"],
        ["change", "archive", CHANGE, "--memory", "none"],
        ["change", "archive", CHANGE, "--note", "x"],
    ],
)
def test_archive_option_conflicts(tmp_path: Path, args):
    home = home_fixture(tmp_path)
    code, result = invoke(home, *args)
    assert code == 1 and result["error"] == "option_conflict"


@pytest.mark.parametrize(
    "module",
    [
        "schema_loader",
        "legacy_workflow",
        "artifacts",
        "paths",
        "workflow_snapshot",
        "workflow_drafts",
        "workflow_confirmation",
        "workflow_recovery",
        "workflow_approval",
    ],
)
def test_removed_modules_cannot_be_imported(module):
    import importlib

    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("loopspec." + module)


# ---------------------------------------------------------------- registry


def registry_home(tmp_path: Path) -> Path:
    from tests.registry_helpers import registry_project

    return registry_project(tmp_path)[1]


def test_registry_not_configured(tmp_path: Path):
    home = home_fixture(tmp_path)
    for args in (["registry", "update"], ["registry", "apply", "--plan", "0" * 64]):
        code, body = invoke(home, *args)
        assert code == 1 and body["error"] == "registry_not_configured"


def test_registry_update_apply_cli(tmp_path: Path):
    home = registry_home(tmp_path)
    code, plan = invoke(home, "registry", "update")
    assert code == 0
    assert {
        "registry",
        "upToDate",
        "baseCommit",
        "baseTag",
        "upstreamCommit",
        "upstreamTag",
        "baseAvailable",
        "migration",
        "planId",
        "definitions",
        "files",
        "localConflicts",
        "brokenReferences",
        "warnings",
        "nextSteps",
    } <= set(plan)
    code, _ = invoke(
        home, "registry", "apply", "--plan", plan["planId"], "--skip", "profiles/bugfix.yaml"
    )
    assert code == 2  # --skip / --resolve no longer exist
    code, body = invoke(home, "registry", "apply", "--plan", plan["planId"])
    assert code == 0 and body["applied"] is True
    assert {"added", "modified", "deleted", "lock"} <= set(body)
    code, body = invoke(home, "registry", "update", "--full")
    assert code == 0 and body["upToDate"] is False
    assert invoke(home, "registry", "update")[1]["upToDate"] is True


def test_list_reports_registry_source(tmp_path: Path):
    from tests.registry_helpers import local_fragment

    home = registry_home(tmp_path)
    code, body = invoke(home, "fragment", "list")
    assert code == 1 and body["error"] == "registry_not_synced"
    plan = invoke(home, "registry", "update")[1]
    invoke(home, "registry", "apply", "--plan", plan["planId"])
    local_fragment(home, "local-only")
    fragments = {i["name"]: i for i in invoke(home, "fragment", "list")[1]["fragments"]}
    assert fragments["design"]["source"] == "registry"
    assert fragments["design"]["registry"] == {
        "syncedTag": "v1.0.0",
        "syncedCommit": plan["upstreamCommit"],
    }
    assert fragments["local-only"]["source"] == "local"
    assert fragments["local-only"]["registry"] is None
    profiles = {i["name"]: i for i in invoke(home, "profile", "list")[1]["profiles"]}
    assert profiles["bugfix"]["registry"]["syncedTag"] == "v1.0.0"
    (home / "registry.lock.yaml").write_text(":::")
    code, body = invoke(home, "profile", "list")
    assert code == 1 and body["error"] == "config_invalid"


def test_profile_save_refuses_registry_names(tmp_path: Path):
    from tests.registry_helpers import sync
    from tests.workflow_helpers import DOCS_FLOW, create_approved

    home = registry_home(tmp_path)
    sync(home)
    create_approved(home, DOCS_FLOW)
    code, body = invoke(home, "profile", "save", "bugfix", "-c", "AFD1111")
    assert code == 1 and body["error"] == "profile_exists"
    assert not (home / "profiles").exists()
    code, body = invoke(home, "profile", "save", "docs-only", "-c", "AFD1111")
    assert code == 0 and body["saved"] == "profiles/docs-only.yaml"
    profiles = {i["name"]: i for i in invoke(home, "profile", "list")[1]["profiles"]}
    assert profiles["docs-only"]["source"] == "local"


def test_graph_profile_in_registry_mode(tmp_path: Path):
    from tests.registry_helpers import sync

    home = registry_home(tmp_path)
    sync(home)
    code, body = invoke(home, "graph", "--profile", "bugfix", "--no-open", "--json")
    assert code == 0 and body["nodes"] > 0, body
