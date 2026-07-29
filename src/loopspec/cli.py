"""Typer CLI entry point."""

from __future__ import annotations

import importlib.metadata
import importlib.resources
import json
import re
import shutil
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, NoReturn

import typer

from . import config as config_mod
from . import paths as paths_mod
from .attempts import list_rounds
from .change_state import create_initial_state
from .errors import (
    ArchiveConflictError,
    ArchiveUnsafeError,
    ChangeExistsError,
    ChangeNotFoundError,
    InvalidChangeNameError,
    LoopspecError,
    SchemaSelectionRequiredError,
)
from .instructions import build_instructions
from .models import KEBAB_RE
from .policy import build_next_steps
from .presentation import Presenter, render_init_summary
from .rollback import compute_reset_closure, rollback_change
from .scaffold import ScaffoldResult, scaffold_tools
from .schema_loader import load_schema
from .state import compute_states, is_complete
from .task_tracking import progress_summary, read_task_progress
from .tool_registry import AI_TOOLS
from .tools_cli import is_interactive, prompt_tools_interactively, resolve_tools_arg

app = typer.Typer(help="loopspec: a gated artifact workflow CLI.")
schemas_app = typer.Typer(help="Manage workflow schemas.")
app.add_typer(schemas_app, name="schemas")

_KEBAB = re.compile(KEBAB_RE)
DEFAULT_HOME = Path("./loopspec")

HomeOption = typer.Option(DEFAULT_HOME, "--home", help="Workflow home directory.")
JsonOption = typer.Option(False, "--json", help="Emit machine-readable JSON.")
HomePathArgument = typer.Argument(DEFAULT_HOME)
NoBuiltinOption = typer.Option(False, "--no-builtin", help="Skip copying built-in schemas.")
ToolsOption = typer.Option(
    None,
    "--tools",
    help=(
        "all|none|comma-separated tool ids (e.g. claude,codex) to scaffold "
        "skills/commands for. Defaults to none when not run interactively."
    ),
)
ProjectRootOption = typer.Option(
    None,
    "--project-root",
    help=(
        "Where to write AI-tool skill/command dirs (.claude, .codex, ...). "
        "Defaults to the parent of the workflow home, i.e. your project root."
    ),
)


def _emit(data: dict[str, Any], as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(data, indent=2, default=str))
    else:
        for key, value in data.items():
            typer.echo(f"{key}: {value}")


def _fail(exc: LoopspecError, as_json: bool, extra: dict[str, Any] | None = None) -> NoReturn:
    payload = exc.to_dict()
    if extra:
        payload.update(extra)
    _emit(payload, as_json)
    raise typer.Exit(code=1)


@dataclass
class ChangeContext:
    change_name: str
    config: Any
    change_dir: Path
    artifact_dir: Path
    schema_name: str
    loaded: Any


def _load_change_context(home: Path, change_name: str) -> ChangeContext:
    config = config_mod.load_config(home)
    change_dir = paths_mod.change_root(home, config.artifacts_dir, change_name)
    if not change_dir.is_dir():
        raise ChangeNotFoundError(f"Change not found: {change_name}")

    metadata = config_mod.read_metadata(change_dir)
    schema_name = config_mod.resolve_schema_for_existing_change(config, metadata, None)
    schema_dir = paths_mod.schema_dir(home, schema_name)
    loaded = load_schema(schema_dir)
    schema_path = config_mod.schema_path_for(config, schema_name)
    artifact_dir = paths_mod.artifact_root(change_dir, schema_path)
    artifact_dir.mkdir(parents=True, exist_ok=True)

    return ChangeContext(
        change_name=change_name,
        config=config,
        change_dir=change_dir,
        artifact_dir=artifact_dir,
        schema_name=schema_name,
        loaded=loaded,
    )


# --------------------------------------------------------------------------- #
# version
# --------------------------------------------------------------------------- #


@app.command()
def version(as_json: bool = JsonOption) -> None:
    """Print the installed loopspec version."""

    try:
        installed_version = importlib.metadata.version("loopspec")
    except importlib.metadata.PackageNotFoundError:
        from . import __version__ as installed_version  # fallback for source checkouts

    if as_json:
        typer.echo(json.dumps({"version": installed_version}))
    else:
        typer.echo(installed_version)


# --------------------------------------------------------------------------- #
# init
# --------------------------------------------------------------------------- #


DEFAULT_SCHEMA_NAME = "secure-spec-driven"
PROJECT_URL = "https://github.com/mingyuans/LoopSpec"
ISSUES_URL = f"{PROJECT_URL}/issues"


def _display_path(path: Path) -> str:
    """Prefer a cwd-relative path; fall back to absolute when it isn't under cwd."""

    try:
        return str(path.resolve().relative_to(Path.cwd()))
    except ValueError:
        return str(path)


def _scaffold_with_progress(
    root: Path, tool_ids: list[str], presenter: Presenter | None
) -> ScaffoldResult:
    """Scaffold tool-by-tool so each one can report its own completion line."""

    merged = ScaffoldResult()
    for tool_id in tool_ids:
        label = AI_TOOLS[tool_id].label
        if presenter is None:
            partial = scaffold_tools(root, [tool_id])
        else:
            with presenter.stage(f"Setting up {label}...", f"Setup complete for {label}"):
                partial = scaffold_tools(root, [tool_id])
        merged.written_files.update(partial.written_files)
        merged.skipped_command_generation.extend(partial.skipped_command_generation)
        merged.created.extend(partial.created)
        merged.refreshed.extend(partial.refreshed)
    return merged


def _init_counts(result: ScaffoldResult) -> tuple[int, int]:
    written = [path for paths in result.written_files.values() for path in paths]
    skills = sum(1 for path in written if path.endswith("SKILL.md"))
    return skills, len(written) - skills


def _builtin_schemas_source() -> Path:
    """Locate the bundled built-in schemas.

    Normal installs get `builtin_schemas/` copied inside the package (see
    `[tool.hatch.build.targets.wheel.force-include]`); editable/source
    checkouts resolve straight to `src/loopspec`, which doesn't have that
    copy, so fall back to the repo-root `schemas/` directory in that case.
    """

    packaged = Path(str(importlib.resources.files("loopspec") / "builtin_schemas"))
    if packaged.is_dir() and any(packaged.iterdir()):
        return packaged
    return Path(__file__).resolve().parent.parent.parent / "schemas"


@app.command()
def init(
    path: Path = HomePathArgument,
    no_builtin: bool = NoBuiltinOption,
    tools: str | None = ToolsOption,
    project_root: Path | None = ProjectRootOption,
    as_json: bool = JsonOption,
) -> None:
    """Initialize a workflow home."""

    presenter = None if as_json else Presenter()

    path.mkdir(parents=True, exist_ok=True)
    (path / "schemas").mkdir(exist_ok=True)
    (path / "changes").mkdir(exist_ok=True)

    config_path = path / "config.yaml"
    created_files = []
    if not config_path.is_file():
        config_path.write_text(
            f"artifacts_dir: changes\nschema: {DEFAULT_SCHEMA_NAME}\n", encoding="utf-8"
        )
        created_files.append("config.yaml")

    copied_schemas: list[str] = []
    if not no_builtin:
        source = _builtin_schemas_source()
        if source.is_dir():
            for candidate in sorted(p for p in source.iterdir() if p.is_dir()):
                destination = path / "schemas" / candidate.name
                if not destination.exists():
                    shutil.copytree(candidate, destination)
                    copied_schemas.append(candidate.name)

    if presenter is not None:
        presenter.line(presenter.ready(f"Workflow home ready at {_display_path(path)}"))

    # AI tools look for `.claude/`, `.codex/`, ... at the *project* root, not
    # inside the workflow home, so scaffold into the workflow home's parent
    # unless the caller pointed us somewhere else explicitly. Resolved before the
    # prompt so the tool list can report each tool's current state there.
    scaffold_root = (project_root or path.resolve().parent).resolve()

    try:
        if tools is None:
            tool_ids = prompt_tools_interactively(scaffold_root) if is_interactive() else []
        else:
            tool_ids = resolve_tools_arg(tools)
    except LoopspecError as exc:
        _fail(exc, as_json)

    scaffold_result = _scaffold_with_progress(scaffold_root, tool_ids, presenter)

    result = {
        "workflowHome": str(path.resolve()),
        "projectRoot": str(scaffold_root),
        "createdFiles": created_files,
        "copiedSchemas": copied_schemas,
        "toolsConfigured": tool_ids,
        "scaffoldedFiles": scaffold_result.written_files,
        "skippedCommandGeneration": scaffold_result.skipped_command_generation,
        "createdTools": scaffold_result.created,
        "refreshedTools": scaffold_result.refreshed,
        "nextSteps": [
            f"Run `loopspec schemas list --home {path} --json` to see available schemas."
        ],
    }

    if presenter is None:
        _emit(result, as_json)
        return

    skill_count, command_count = _init_counts(scaffold_result)
    home_suffix = "" if path == DEFAULT_HOME else f" --home {path}"
    render_init_summary(
        presenter,
        created=[AI_TOOLS[tool_id].label for tool_id in scaffold_result.created],
        refreshed=[AI_TOOLS[tool_id].label for tool_id in scaffold_result.refreshed],
        skill_count=skill_count,
        command_count=command_count,
        tool_dirs=list(dict.fromkeys(AI_TOOLS[tool_id].skills_dir for tool_id in tool_ids)),
        skipped_command_generation=scaffold_result.skipped_command_generation,
        config_path=_display_path(config_path),
        schema_name=DEFAULT_SCHEMA_NAME if "config.yaml" in created_files else None,
        getting_started=f"loopspec new <change-name>{home_suffix}",
        project_url=PROJECT_URL,
        issues_url=ISSUES_URL,
    )


# --------------------------------------------------------------------------- #
# schemas list / show / validate
# --------------------------------------------------------------------------- #


@schemas_app.command("list")
def schemas_list(home: Path = HomeOption, as_json: bool = JsonOption) -> None:
    schemas_dir = home / "schemas"
    entries = []
    if schemas_dir.is_dir():
        for candidate in sorted(p for p in schemas_dir.iterdir() if p.is_dir()):
            if not (candidate / "schema.yaml").is_file():
                continue
            try:
                loaded = load_schema(candidate)
            except LoopspecError:
                continue
            entries.append(
                {
                    "name": loaded.schema.name,
                    "version": loaded.schema.version,
                    "source": "local",
                    "path": str(candidate.resolve()),
                    "nodes": loaded.graph.node_ids(),
                }
            )
    _emit({"schemas": entries}, as_json)


@schemas_app.command("show")
def schemas_show(name: str, home: Path = HomeOption, as_json: bool = JsonOption) -> None:
    try:
        loaded = load_schema(paths_mod.schema_dir(home, name))
    except LoopspecError as exc:
        _fail(exc, as_json)

    nodes = []
    for node_id in loaded.graph.build_order():
        node = loaded.node(node_id)
        nodes.append(
            {
                "id": node.id,
                "requires": node.requires,
                "generates": node.generates,
                "isGate": node.gate is not None,
            }
        )
    _emit({"name": loaded.schema.name, "version": loaded.schema.version, "nodes": nodes}, as_json)


@schemas_app.command("validate")
def schemas_validate(name: str, home: Path = HomeOption, as_json: bool = JsonOption) -> None:
    try:
        loaded = load_schema(paths_mod.schema_dir(home, name))
    except LoopspecError as exc:
        _fail(exc, as_json)

    _emit(
        {"valid": True, "name": loaded.schema.name, "buildOrder": loaded.graph.build_order()},
        as_json,
    )


# --------------------------------------------------------------------------- #
# new
# --------------------------------------------------------------------------- #


@app.command()
def new(
    change_name: str,
    schema: str | None = typer.Option(None, "--schema"),
    home: Path = HomeOption,
    as_json: bool = JsonOption,
) -> None:
    if not _KEBAB.match(change_name):
        _fail(InvalidChangeNameError(f"Invalid change name: {change_name}"), as_json)

    try:
        config = config_mod.load_config(home)
    except LoopspecError as exc:
        _fail(exc, as_json)

    change_dir = paths_mod.change_root(home, config.artifacts_dir, change_name)
    if change_dir.exists():
        _fail(ChangeExistsError(f"Change already exists: {change_name}"), as_json)

    try:
        schema_name = config_mod.resolve_schema_for_new_change(config, schema)
    except SchemaSelectionRequiredError as exc:
        payload: dict[str, Any] = exc.to_dict()
        payload.update(
            {
                "changeName": change_name,
                "artifactsDir": config.artifacts_dir,
                "schemas": [
                    {
                        "name": ref.name,
                        "path": ref.path,
                        "description": ref.description,
                        "when": ref.when,
                    }
                    for ref in config.schemas
                ],
                "selectionInstruction": (
                    config.schema_selection.instruction if config.schema_selection else None
                ),
            }
        )
        _emit(payload, as_json)
        raise typer.Exit(code=1) from None
    except LoopspecError as exc:
        _fail(exc, as_json)

    try:
        load_schema(paths_mod.schema_dir(home, schema_name))
    except LoopspecError as exc:
        _fail(exc, as_json)

    schema_path = config_mod.schema_path_for(config, schema_name)
    artifact_root = paths_mod.artifact_root(change_dir, schema_path)

    change_dir.mkdir(parents=True)
    artifact_root.mkdir(parents=True, exist_ok=True)
    created = date.today().isoformat()
    metadata_path = config_mod.write_metadata(change_dir, schema_name, created)
    state_path = create_initial_state(change_dir)

    result = {
        "changeName": change_name,
        "schemaName": schema_name,
        "artifactsDir": config.artifacts_dir,
        "schemaPath": schema_path,
        "changeRoot": str(change_dir.resolve()),
        "artifactRoot": str(artifact_root.resolve()),
        "statePath": str(state_path.resolve()),
        "metadataPath": str(metadata_path.resolve()),
        "created": created,
        "createdFiles": [".workflow.yaml", "state.md"],
        "nextSteps": [f'Run `loopspec status {change_name} --json` to see the first node.'],
    }
    _emit(result, as_json)


# --------------------------------------------------------------------------- #
# status
# --------------------------------------------------------------------------- #


def _node_output_summary(loaded, node_id: str, artifact_dir: Path) -> dict[str, Any]:
    node = loaded.node(node_id)
    summary: dict[str, Any]
    if node.gate is None:
        resolved = artifact_dir / node.generates
        existing = [str(resolved.resolve())] if resolved.is_file() else []
        summary = {
            "outputPath": node.generates,
            "resolvedOutputPath": str((artifact_dir / node.generates).resolve()),
            "existingOutputPaths": existing,
        }
    else:
        pass_path = artifact_dir / node.gate.outputs.pass_
        fail_path = artifact_dir / node.gate.outputs.fail
        existing = [str(p.resolve()) for p in (pass_path, fail_path) if p.is_file()]
        summary = {
            "outputPath": {"pass": node.gate.outputs.pass_, "fail": node.gate.outputs.fail},
            "resolvedOutputPath": {
                "pass": str(pass_path.resolve()),
                "fail": str(fail_path.resolve()),
            },
            "existingOutputPaths": existing,
        }

    if node.tracks is not None:
        # Counts only -- the per-task list stays in `loopspec instructions`, since
        # `status` is called on every turn of the loop and must stay compact.
        summary["taskProgress"] = progress_summary(read_task_progress(artifact_dir, node.tracks))
    return summary


@app.command()
def status(change_name: str, home: Path = HomeOption, as_json: bool = JsonOption) -> None:
    try:
        ctx = _load_change_context(home, change_name)
    except LoopspecError as exc:
        _fail(exc, as_json)

    states = compute_states(ctx.loaded.graph, ctx.change_dir, ctx.artifact_dir)
    nodes = []
    pending_rollback = None
    for node_id in ctx.loaded.graph.build_order():
        state = states[node_id]
        entry: dict[str, Any] = {"id": node_id, "status": state.status}
        entry.update(_node_output_summary(ctx.loaded, node_id, ctx.artifact_dir))
        if state.status in ("failed", "exhausted"):
            node = ctx.loaded.node(node_id)
            assert node.gate is not None and state.verdict is not None
            closure = compute_reset_closure(ctx.loaded.graph, node_id)
            entry["gate"] = {
                "verdict": state.verdict.status,
                "summary": state.verdict.summary,
                "blockingIssues": state.verdict.blocking_issues,
                "rollbacksUsed": state.rollbacks_used,
                "maxRetries": state.max_retries,
                "resetDeclared": node.gate.on_fail.reset,
                "resetClosure": closure,
            }
            if state.status == "failed" and pending_rollback is None:
                pending_rollback = {
                    "gate": node_id,
                    "closure": closure,
                    "command": f"loopspec rollback {change_name} --json",
                }
        elif state.status == "blocked":
            entry["missingDeps"] = state.missing_deps
        nodes.append(entry)

    state_path = ctx.change_dir / "state.md"
    result = {
        "changeName": change_name,
        "schemaName": ctx.schema_name,
        "artifactsDir": ctx.config.artifacts_dir,
        "schemaPath": config_mod.schema_path_for(ctx.config, ctx.schema_name),
        "changeRoot": str(ctx.change_dir.resolve()),
        "artifactRoot": str(ctx.artifact_dir.resolve()),
        "statePath": str(state_path.resolve()),
        "stateExists": state_path.is_file(),
        "isComplete": is_complete(states),
        "nodes": nodes,
        "pendingRollback": pending_rollback,
        "nextSteps": build_next_steps(change_name, ctx.loaded.graph, states),
    }
    _emit(result, as_json)


# --------------------------------------------------------------------------- #
# instructions
# --------------------------------------------------------------------------- #


@app.command()
def instructions(
    node_id: str,
    change: str = typer.Option(..., "--change"),
    home: Path = HomeOption,
    as_json: bool = JsonOption,
) -> None:
    try:
        ctx = _load_change_context(home, change)
    except LoopspecError as exc:
        _fail(exc, as_json)

    try:
        response = build_instructions(
            ctx.loaded,
            node_id,
            ctx.change_dir,
            ctx.artifact_dir,
            context=ctx.config.context,
            rules_by_node=ctx.config.rules,
        )
    except LoopspecError as exc:
        _fail(exc, as_json)

    response = {
        "changeName": change,
        "schemaName": ctx.schema_name,
        "changeDir": str(ctx.change_dir.resolve()),
        "artifactRoot": str(ctx.artifact_dir.resolve()),
        **response,
    }
    _emit(response, as_json)


# --------------------------------------------------------------------------- #
# rollback
# --------------------------------------------------------------------------- #


@app.command()
def rollback(change_name: str, home: Path = HomeOption, as_json: bool = JsonOption) -> None:
    try:
        ctx = _load_change_context(home, change_name)
    except LoopspecError as exc:
        _fail(exc, as_json)

    try:
        result = rollback_change(ctx.loaded.graph, ctx.change_dir, ctx.artifact_dir)
    except LoopspecError as exc:
        _fail(exc, as_json)

    payload = {
        "changeName": change_name,
        "gate": result.gate,
        "round": result.round,
        "closure": result.closure,
        "archivedFiles": result.archived,
        "archiveDir": str(result.archive_dir.resolve()),
        "rollbacksUsed": result.rollbacks_used,
        "maxRetries": result.max_retries,
        "nextSteps": [f"Run `loopspec status {change_name} --json` to see the next node."],
    }
    _emit(payload, as_json)


# --------------------------------------------------------------------------- #
# history
# --------------------------------------------------------------------------- #


@app.command()
def history(change_name: str, home: Path = HomeOption, as_json: bool = JsonOption) -> None:
    try:
        ctx = _load_change_context(home, change_name)
    except LoopspecError as exc:
        _fail(exc, as_json)

    rounds = []
    for meta in list_rounds(ctx.change_dir):
        round_dir: Path = meta["_dir"]
        rounds.append(
            {
                "round": meta.get("round"),
                "gate": meta.get("gate"),
                "verdict": meta.get("verdict"),
                "summary": meta.get("summary"),
                "resetClosure": meta.get("reset_closure"),
                "archivedFiles": meta.get("archived_files"),
                "archiveDir": str(round_dir.resolve()),
                "archivedAt": meta.get("archived_at"),
            }
        )
    _emit({"changeName": change_name, "rounds": rounds}, as_json)


# --------------------------------------------------------------------------- #
# archive / bulk-archive
# --------------------------------------------------------------------------- #


def _change_archive_reason(
    graph, change_dir: Path, artifact_dir: Path, allow_exhausted: bool, allow_pending_failures: bool
) -> str:
    states = compute_states(graph, change_dir, artifact_dir)
    if is_complete(states):
        return "complete"

    statuses = {state.status for state in states.values()}
    if "exhausted" in statuses and allow_exhausted and "failed" not in statuses:
        return "exhausted"
    if "failed" in statuses and allow_pending_failures:
        return "pending-failure"

    raise ArchiveUnsafeError(
        "This change is not complete and does not qualify for archiving under the "
        "current flags.",
        fix="Finish the change, or pass --exhausted / --include-pending-failures "
        "if that applies.",
    )


def _archive_one(
    home: Path,
    change_name: str,
    *,
    dry_run: bool,
    allow_exhausted: bool,
    allow_pending_failures: bool,
    today: date,
) -> dict[str, Any]:
    ctx = _load_change_context(home, change_name)
    reason = _change_archive_reason(
        ctx.loaded.graph, ctx.change_dir, ctx.artifact_dir, allow_exhausted, allow_pending_failures
    )

    year_month = today.strftime("%Y-%m")
    destination = (paths_mod.archive_root(home, year_month) / change_name).resolve()

    result: dict[str, Any] = {
        "dryRun": dry_run,
        "changeName": change_name,
        "schemaName": ctx.schema_name,
        "reason": reason,
        "source": str(ctx.change_dir.resolve()),
        "destination": str(destination),
    }

    if dry_run:
        result["nextSteps"] = ["Re-run without --dry-run to move this change into the archive."]
        return result

    if destination.exists():
        raise ArchiveConflictError(f"Archive destination already exists: {destination}")

    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(ctx.change_dir), str(destination))
    result["moved"] = True
    result["nextSteps"] = ["Archiving complete."]
    return result


@app.command()
def archive(
    change_name: str,
    dry_run: bool = typer.Option(False, "--dry-run"),
    exhausted: bool = typer.Option(False, "--exhausted"),
    include_pending_failures: bool = typer.Option(False, "--include-pending-failures"),
    home: Path = HomeOption,
    as_json: bool = JsonOption,
) -> None:
    try:
        result = _archive_one(
            home,
            change_name,
            dry_run=dry_run,
            allow_exhausted=exhausted,
            allow_pending_failures=include_pending_failures,
            today=datetime.now(UTC).date(),
        )
    except LoopspecError as exc:
        _fail(exc, as_json)
    _emit(result, as_json)


@app.command("bulk-archive")
def bulk_archive(
    complete: bool = typer.Option(True, "--complete"),
    exhausted: bool = typer.Option(False, "--exhausted"),
    older_than: int | None = typer.Option(None, "--older-than"),
    dry_run: bool = typer.Option(False, "--dry-run"),
    home: Path = HomeOption,
    as_json: bool = JsonOption,
) -> None:
    changes_dir = home / "changes"
    today = datetime.now(UTC).date()
    year_month = today.strftime("%Y-%m")
    archive_dir = paths_mod.archive_root(home, year_month)

    candidates: list[dict[str, Any]] = []
    moved: list[dict[str, Any]] = []
    if changes_dir.is_dir():
        for change_path in sorted(p for p in changes_dir.iterdir() if p.is_dir()):
            if older_than is not None:
                age_days = (
                    datetime.now(UTC).timestamp() - change_path.stat().st_mtime
                ) / 86400
                if age_days < older_than:
                    continue
            try:
                result = _archive_one(
                    home,
                    change_path.name,
                    dry_run=True,
                    allow_exhausted=exhausted,
                    allow_pending_failures=False,
                    today=today,
                )
            except LoopspecError:
                continue
            candidates.append(result)

    if not dry_run:
        for candidate in candidates:
            result = _archive_one(
                home,
                candidate["changeName"],
                dry_run=False,
                allow_exhausted=exhausted,
                allow_pending_failures=False,
                today=today,
            )
            moved.append(result)

    payload: dict[str, Any] = {
        "dryRun": dry_run,
        "archiveRoot": str(archive_dir),
        "candidates": candidates,
    }
    if not dry_run:
        payload["moved"] = moved
        payload["nextSteps"] = ["Archiving complete."]
    else:
        payload["nextSteps"] = ["Re-run without --dry-run to move these changes into the archive."]
    _emit(payload, as_json)


if __name__ == "__main__":
    app()
