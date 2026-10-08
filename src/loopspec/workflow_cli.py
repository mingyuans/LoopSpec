"""`loopspec <resource> <verb>` workflow commands; every one of them prints JSON."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Any

import typer
from pydantic import ValidationError

from .errors import LoopspecError, WorkflowError
from .workflow_catalog import WorkflowCatalog
from .workflow_compiler import FragmentExpander, build_order
from .workflow_io import exists, write_yaml
from .workflow_models import Profile
from .workflow_planning import validate_profile

HOME = typer.Option(Path("./loopspec"), "--home", help="Workflow home directory.")
CHANGE = typer.Option(..., "-c", "--change", help="Change name.")
PLAN = typer.Option(..., "-p", "--plan", help="Plan number, e.g. 001.")
NODE = typer.Option(..., "-n", "--node", help="Leaf node or Gate path in the active Plan.")
FILE = typer.Option(..., "-f", "--file", help="Request file, relative to the workflow home.")
NOTE = typer.Option(None, "--note", help="Optional note recorded on the Plan.")
FULL = typer.Option(False, "--full", help="Skip the ls-remote version check and always compare.")
REGISTRY_PLAN = typer.Option(..., "--plan", help="planId from `registry update`.")
RESOLVE = typer.Option(
    [], "--resolve", help="Resolve a conflict: <path>=local|upstream. Repeatable."
)
SKIP = typer.Option([], "--skip", help="Leave a pending upstream change out. Repeatable.")


def emit(value: Any) -> None:
    typer.echo(json.dumps(value, ensure_ascii=False, indent=2, default=str))


def run(action: Callable[[], Any]) -> None:
    try:
        emit(action())
    except LoopspecError as exc:
        emit(exc.to_dict())
        raise typer.Exit(1) from None
    except (ValidationError, ValueError):
        emit(WorkflowError("workflow_invalid", "输入结构不合法").to_dict())
        raise typer.Exit(1) from None


def register(app: typer.Typer) -> None:
    change = typer.Typer(help="Create, inspect and archive Changes.", no_args_is_help=True)
    plan = typer.Typer(
        help="Draft, confirm, revise, archive and roll back Plans.", no_args_is_help=True
    )
    node = typer.Typer(help="Execute leaf nodes of the active Plan.", no_args_is_help=True)
    gate = typer.Typer(help="Record review evidence for Gates.", no_args_is_help=True)
    fragment = typer.Typer(help="Browse and validate Fragments.", no_args_is_help=True)
    profile = typer.Typer(help="Browse, validate and save Profiles.", no_args_is_help=True)
    registry = typer.Typer(
        help="Sync fragments and profiles from the configured git registry.",
        no_args_is_help=True,
    )
    app.add_typer(change, name="change")
    app.add_typer(plan, name="plan")
    app.add_typer(node, name="node")
    app.add_typer(gate, name="gate")
    app.add_typer(fragment, name="fragment")
    app.add_typer(profile, name="profile")
    app.add_typer(registry, name="registry")

    # ------------------------------------------------------------------ change

    @change.command("new")
    def change_new(name: str, home: Path = HOME) -> None:
        """Create an unplanned Change."""
        from .workflow_changes import create

        run(lambda: create(home, name))

    @change.command("status")
    def change_status(name: str, home: Path = HOME) -> None:
        """Derived status, node states and the single next step."""
        from .workflow_changes import status

        run(lambda: status(home, name))

    @change.command("next")
    def change_next(name: str, home: Path = HOME) -> None:
        """Only the next step, for agent loops."""
        from .workflow_changes import next_step

        run(lambda: next_step(home, name))

    @change.command("history")
    def change_history(
        name: str,
        plan_id: str | None = typer.Option(None, "-p", "--plan", help="Plan number."),
        home: Path = HOME,
    ) -> None:
        """Rework records (.attempts) of the active or given Plan."""
        from .workflow_changes import history

        run(lambda: history(home, name, plan_id))

    @change.command("artifacts")
    def change_artifacts(name: str, home: Path = HOME) -> None:
        """All artifacts of the Change grouped by Plan, archived ones included."""
        from .workflow_changes import artifacts

        run(lambda: artifacts(home, name))

    @change.command("archive")
    def change_archive(
        name: str | None = typer.Argument(None),
        all_changes: bool = typer.Option(False, "--all", help="Archive every complete Change."),
        older_than: int | None = typer.Option(None, "--older-than", min=0, help="Days."),
        force: bool = typer.Option(False, "--force", help="Archive an unfinished Change."),
        dry_run: bool = typer.Option(False, "--dry-run"),
        home: Path = HOME,
    ) -> None:
        """Move a complete Change (or, with --force, an abandoned one) to archive/."""
        from .workflow_archive import archive, archive_all

        def action() -> dict:
            if all_changes == (name is not None):
                raise WorkflowError("option_conflict", "指定一个需求名，或使用 --all")
            if all_changes and force:
                raise WorkflowError("option_conflict", "--all 不能与 --force 同时使用")
            if older_than is not None and not all_changes:
                raise WorkflowError("option_conflict", "--older-than 只用于 --all")
            if all_changes:
                return archive_all(home, older_than=older_than, dry_run=dry_run, today=date.today())
            assert name is not None
            return archive(home, name, force=force, dry_run=dry_run, today=date.today())

        run(action)

    # -------------------------------------------------------------------- plan

    @plan.command("validate")
    def plan_validate(change_name: str = CHANGE, path: str = FILE, home: Path = HOME) -> None:
        """Read-only compile and check; previews a revision when a Plan is approved."""
        from .workflow_plans import validate

        run(lambda: validate(home, change_name, path))

    @plan.command("create")
    def plan_create(
        change_name: str = CHANGE, path: str = FILE, note: str | None = NOTE, home: Path = HOME
    ) -> None:
        """Create the draft Plan, or replace the spec of the current draft."""
        from .workflow_plans import create

        run(lambda: create(home, change_name, path, note))

    @plan.command("show")
    def plan_show(
        change_name: str = CHANGE,
        plan_id: str | None = typer.Option(None, "-p", "--plan", help="Plan number."),
        home: Path = HOME,
    ) -> None:
        """Show meta and spec of the open Plan, or of the given Plan."""
        from .workflow_plans import show

        run(lambda: show(home, change_name, plan_id))

    @plan.command("list")
    def plan_list(change_name: str = CHANGE, home: Path = HOME) -> None:
        """List every Plan of the Change."""
        from .workflow_plans import plan_list as listing

        run(lambda: listing(home, change_name))

    @plan.command("approve")
    def plan_approve(
        change_name: str = CHANGE,
        plan_id: str = PLAN,
        digest: str = typer.Option(..., "--digest", help="Digest the human confirmed."),
        path: str | None = typer.Option(None, "-f", "--file", help="Revision request file."),
        home: Path = HOME,
    ) -> None:
        """Confirm a draft Plan, or (with -f) a revision; only after a human confirmed it."""
        from .workflow_plans import approve

        run(lambda: approve(home, change_name, plan_id, digest, path))

    @plan.command("archive")
    def plan_archive(
        change_name: str = CHANGE, plan_id: str = PLAN, note: str | None = NOTE, home: Path = HOME
    ) -> None:
        """Archive the draft or approved Plan; an approved one needs the human's consent first."""
        from .workflow_plans import archive

        run(lambda: archive(home, change_name, plan_id, note))

    @plan.command("rollback")
    def plan_rollback(change_name: str = CHANGE, plan_id: str = PLAN, home: Path = HOME) -> None:
        """Rework a failed Gate by its own on_fail; business code is never reverted."""
        from .workflow_plans import rollback

        run(lambda: rollback(home, change_name, plan_id))

    # -------------------------------------------------------------------- node

    @node.command("instructions")
    def node_instructions(
        change_name: str = CHANGE, identity: str = NODE, home: Path = HOME
    ) -> None:
        """Everything needed to execute one leaf node of the active Plan."""
        from .workflow_runtime import instructions
        from .workflow_state import open_change

        def action() -> dict:
            from .workflow_attempts import settled
            from .workflow_io import write_lock

            # Finish archiving an effective rework record before the agent writes new outputs.
            with write_lock(open_change(home, change_name).root):
                return instructions(settled(open_change(home, change_name)), identity)

        run(action)

    # -------------------------------------------------------------------- gate

    @gate.command("begin")
    def gate_begin(change_name: str = CHANGE, identity: str = NODE, home: Path = HOME) -> None:
        """Pin the code under review for a code Gate and get a one-time round id."""
        from .workflow_evidence import begin

        run(lambda: begin(home, change_name, identity))

    @gate.command("record")
    def gate_record(
        change_name: str = CHANGE,
        identity: str = NODE,
        round_id: str | None = typer.Option(None, "--round", help="Round id from gate begin."),
        report: str | None = typer.Option(None, "--report", help="Report under artifacts/."),
        home: Path = HOME,
    ) -> None:
        """Record a code Gate verdict, or run the system check of an assurance node."""
        from .workflow_evidence import record

        run(lambda: record(home, change_name, identity, round_id, report))

    # ---------------------------------------------------------------- fragment

    @fragment.command("list")
    def fragment_list(home: Path = HOME) -> None:
        def action() -> dict:
            from .registry_sync import synced_versions

            versions = synced_versions(home)
            return {
                "fragments": [
                    {
                        **item.model_dump(by_alias=True),
                        "registry": versions.get("fragments/" + item.name),
                    }
                    for item in WorkflowCatalog(home).entries("fragments")
                ]
            }

        run(action)

    @fragment.command("show")
    def fragment_show(name: str, home: Path = HOME) -> None:
        run(lambda: WorkflowCatalog(home).fragment(name).model_dump(by_alias=True))

    @fragment.command("validate")
    def fragment_validate(name: str, home: Path = HOME) -> None:
        def action() -> dict:
            expanded = FragmentExpander(WorkflowCatalog(home))
            expanded.expand(name, "fragment")
            expanded.connect()
            expanded.validate()
            expanded.resolve_nodes()
            return {"valid": True, "buildOrder": build_order(expanded.dependencies)}

        run(action)

    # ----------------------------------------------------------------- profile

    @profile.command("list")
    def profile_list(home: Path = HOME) -> None:
        def action() -> dict:
            from .registry_sync import synced_versions

            versions = synced_versions(home)
            return {
                "profiles": [
                    {
                        **item.model_dump(by_alias=True, exclude_none=True),
                        "registry": versions.get("profiles/" + item.name),
                    }
                    for item in WorkflowCatalog(home).entries("profiles")
                ]
            }

        run(action)

    @profile.command("show")
    def profile_show(name: str, home: Path = HOME) -> None:
        run(
            lambda: WorkflowCatalog(home).profile(name).model_dump(by_alias=True, exclude_none=True)
        )

    @profile.command("validate")
    def profile_validate(name: str, home: Path = HOME) -> None:
        def action() -> dict:
            catalog = WorkflowCatalog(home)
            return validate_profile(catalog, catalog.profile(name))

        run(action)

    @profile.command("save")
    def profile_save(name: str, change_name: str = CHANGE, home: Path = HOME) -> None:
        """Save the active Plan's flow as a new Profile; never overwrites."""

        def action() -> dict:
            from .workflow_state import active_plan, open_change

            loaded = active_plan(open_change(home, change_name))
            profile = Profile(
                name=name,
                description="从需求 Plan 保存的工作流模板",
                flow=loaded.spec.flow,
            )
            validate_profile(WorkflowCatalog(home), profile)
            path = "profiles/" + profile.name + ".yaml"
            if exists(home, path):
                raise WorkflowError(
                    "profile_exists", "同名 Profile 已存在，不会覆盖", "换一个名称。"
                )
            write_yaml(
                home, path, profile.model_dump(by_alias=True, exclude_none=True), exclusive=True
            )
            return {"saved": path, "includesRuntimeState": False}

        run(action)

    # ---------------------------------------------------------------- registry

    @registry.command("update")
    def registry_update(full: bool = FULL, home: Path = HOME) -> None:
        """Fetch the registry and plan a three-way sync; writes only the cache."""
        from .registry_sync import update

        run(lambda: update(home, full=full))

    @registry.command("apply")
    def registry_apply(
        plan_id: str = REGISTRY_PLAN,
        resolve: list[str] = RESOLVE,
        skip: list[str] = SKIP,
        home: Path = HOME,
    ) -> None:
        """Write a confirmed plan into fragments/ and profiles/ and update the lock."""
        from .registry_sync import apply

        run(lambda: apply(home, plan_id, resolve, skip))
