"""`loopspec <resource> <verb>` workflow commands.

Every command prints a plain-text report written for an LLM to read by default, and
the same payload as JSON with `--json` (see `text_reports` and AGENTS.md).
"""

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


def _sync_skills(value: Path) -> Path:
    """`--home` callback (also for the default): bring the project's skills up to date first."""
    from .skill_sync import sync_before_command

    sync_before_command(value)
    return value


HOME = typer.Option(
    Path("./loopspec"), "--home", help="Workflow home directory.", callback=_sync_skills
)
CHANGE = typer.Option(..., "-c", "--change", help="Change name.")
PLAN = typer.Option(..., "-p", "--plan", help="Plan number, e.g. 001.")
NODE = typer.Option(..., "-n", "--node", help="Leaf node or Gate path in the active Plan.")
FILE = typer.Option(..., "-f", "--file", help="Request file, relative to the workflow home.")
NOTE = typer.Option(None, "--note", help="Optional note recorded on the Plan.")
FULL = typer.Option(False, "--full", help="Skip the ls-remote version check and always compare.")
REGISTRY_PLAN = typer.Option(..., "--plan", help="planId from `registry update`.")
OUTPUT = typer.Option(
    None, "-o", "--output", help="HTML file to write; defaults to <home>/.cache/graph/."
)


JSON_OUTPUT = typer.Option(
    False, "--json", help="Print the JSON payload instead of the text report."
)


def emit(value: Any) -> None:
    typer.echo(json.dumps(value, ensure_ascii=False, indent=2, default=str))


def run(
    action: Callable[[], Any],
    render: Callable[[Any], str] | None = None,
    render_error: Callable[[dict], str] | None = None,
) -> None:
    """JSON without a renderer; `render`/`render_error` print a text report instead.

    The command has already taken effect when its result is rendered, so a renderer
    failure must not look like a failed command: the payload is printed as JSON instead,
    with a note on stderr, and the exit status stays that of the command.
    """

    def output(value: Any, renderer: Callable[[Any], str] | None) -> None:
        if renderer is None:
            emit(value)
            return
        try:
            text = renderer(value)
        except Exception as exc:  # noqa: BLE001 - never turn a done command into a crash
            typer.echo(
                f"loopspec: text report unavailable ({type(exc).__name__}); printing JSON",
                err=True,
            )
            emit(value)
            return
        typer.echo(text, nl=False)

    try:
        value = action()
    except LoopspecError as exc:
        output(exc.to_dict(), render_error)
        raise typer.Exit(1) from None
    except (ValidationError, ValueError):
        output(WorkflowError("workflow_invalid", "输入结构不合法").to_dict(), render_error)
        raise typer.Exit(1) from None
    output(value, render)


def report(action: Callable[[], Any], command: str, as_json: bool) -> None:
    """Text report of `command` by default; the JSON payload with `--json`."""
    if as_json:
        run(action)
        return
    from .status_report import render_error_report
    from .text_reports import RENDERERS

    run(action, RENDERERS[command].render, render_error_report)


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
    state = typer.Typer(
        help="Append records to the Change and Plan state.md.", no_args_is_help=True
    )
    memory = typer.Typer(
        help="Read cross-Change memory topics (memory/{topic}.md).", no_args_is_help=True
    )
    app.add_typer(change, name="change")
    app.add_typer(plan, name="plan")
    app.add_typer(node, name="node")
    app.add_typer(gate, name="gate")
    app.add_typer(fragment, name="fragment")
    app.add_typer(profile, name="profile")
    app.add_typer(registry, name="registry")
    app.add_typer(state, name="state")
    app.add_typer(memory, name="memory")

    # ------------------------------------------------------------------ memory

    @memory.command("list")
    def memory_list(
        offset: int = typer.Option(0, "--offset", help="Skip this many topics (paging)."),
        limit: int = typer.Option(200, "--limit", help="Topics per page (at most 500)."),
        include_ignored: bool = typer.Option(
            False, "--all", help="Also list files in memory/ that are not topics."
        ),
        as_json: bool = JSON_OUTPUT,
        home: Path = HOME,
    ) -> None:
        """The topic index: path, one-line hint and size. `nextOffset` pages to the rest."""
        from .workflow_memory import list_topics

        report(
            lambda: list_topics(home, offset=offset, limit=limit, include_ignored=include_ignored),
            "memory list",
            as_json,
        )

    @memory.command("show")
    def memory_show(topic: str, as_json: bool = JSON_OUTPUT, home: Path = HOME) -> None:
        """The full text of one topic (core included). Untrusted reference data."""
        from .workflow_memory import UNTRUSTED, read_topic

        report(
            lambda: {
                "topic": topic,
                "path": f"memory/{topic}.md",
                "content": read_topic(home, topic),
                "untrustedData": UNTRUSTED,
            },
            "memory show",
            as_json,
        )

    # ------------------------------------------------------------------ change

    @change.command("new")
    def change_new(name: str, as_json: bool = JSON_OUTPUT, home: Path = HOME) -> None:
        """Create an unplanned Change."""
        from .workflow_changes import create

        report(lambda: create(home, name), "change new", as_json)

    @change.command("status")
    def change_status(
        name: str,
        as_json: bool = typer.Option(False, "--json", help="Print the JSON payload instead."),
        home: Path = HOME,
    ) -> None:
        """Plain-text report for an LLM: state records, plans, nodes and the next step."""
        from .workflow_changes import status

        if as_json:
            run(lambda: status(home, name))
            return
        from .status_report import render_error_report, render_status_report

        run(lambda: status(home, name), render_status_report, render_error_report)

    @change.command("next")
    def change_next(name: str, as_json: bool = JSON_OUTPUT, home: Path = HOME) -> None:
        """Only the next step, for agent loops."""
        from .workflow_changes import next_step

        report(lambda: next_step(home, name), "change next", as_json)

    @change.command("history")
    def change_history(
        name: str,
        plan_id: str | None = typer.Option(None, "-p", "--plan", help="Plan number."),
        as_json: bool = JSON_OUTPUT,
        home: Path = HOME,
    ) -> None:
        """Rework records (.attempts) of the active or given Plan."""
        from .workflow_changes import history

        report(lambda: history(home, name, plan_id), "change history", as_json)

    @change.command("artifacts")
    def change_artifacts(name: str, as_json: bool = JSON_OUTPUT, home: Path = HOME) -> None:
        """All artifacts of the Change grouped by Plan, archived ones included."""
        from .workflow_changes import artifacts

        report(lambda: artifacts(home, name), "change artifacts", as_json)

    @change.command("archive")
    def change_archive(
        name: str | None = typer.Argument(None),
        all_changes: bool = typer.Option(False, "--all", help="Prepare every complete Change."),
        older_than: int | None = typer.Option(None, "--older-than", min=0, help="Days."),
        force: bool = typer.Option(False, "--force", help="Archive an unfinished Change."),
        confirm_id: str | None = typer.Option(
            None, "--confirm", help="archiveId from the first step; completes the archive."
        ),
        memory: str | None = typer.Option(
            None, "--memory", help="Memory review outcome: updated or none (with --confirm)."
        ),
        note: str | None = typer.Option(
            None, "--note", help="What was updated in memory, or why nothing was reusable."
        ),
        as_json: bool = JSON_OUTPUT,
        home: Path = HOME,
    ) -> None:
        """Archive in two steps: prepare (review memory), then --confirm the archiveId."""
        from .workflow_archive import confirm, prepare

        def action() -> dict:
            if confirm_id is not None:
                if name is not None or all_changes or force or older_than is not None:
                    raise WorkflowError(
                        "option_conflict",
                        "--confirm 不能与需求名、--all、--force 或 --older-than 同时使用",
                        "第二段只需：loopspec change archive --confirm <archiveId> "
                        "--memory updated|none --note <说明>",
                    )
                if memory is None or note is None:
                    raise WorkflowError(
                        "memory_review_required",
                        "--confirm 必须同时给出 --memory updated|none 与 --note",
                        "先按第一段返回的 memoryReview 完成 memory 审阅，再如实填写结论与说明。",
                    )
                if memory not in ("updated", "none"):
                    raise WorkflowError("workflow_invalid", "--memory 只能是 updated 或 none")
                return confirm(home, confirm_id, memory=memory, note=note, today=date.today())  # type: ignore[arg-type]
            if memory is not None or note is not None:
                raise WorkflowError("option_conflict", "--memory 与 --note 只用于 --confirm 第二段")
            if all_changes == (name is not None):
                raise WorkflowError("option_conflict", "指定一个需求名，或使用 --all")
            if all_changes and force:
                raise WorkflowError("option_conflict", "--all 不能与 --force 同时使用")
            if older_than is not None and not all_changes:
                raise WorkflowError("option_conflict", "--older-than 只用于 --all")
            return prepare(
                home,
                name,
                force=force,
                all_changes=all_changes,
                older_than=older_than,
                today=date.today(),
            )

        report(action, "change archive", as_json)

    # -------------------------------------------------------------------- plan

    @plan.command("validate")
    def plan_validate(
        change_name: str = CHANGE,
        path: str = FILE,
        as_json: bool = JSON_OUTPUT,
        home: Path = HOME,
    ) -> None:
        """Read-only compile and check; previews a revision when a Plan is approved."""
        from .workflow_plans import validate

        report(lambda: validate(home, change_name, path), "plan validate", as_json)

    @plan.command("create")
    def plan_create(
        change_name: str = CHANGE,
        path: str = FILE,
        note: str | None = NOTE,
        as_json: bool = JSON_OUTPUT,
        home: Path = HOME,
    ) -> None:
        """Create the draft Plan, or replace the spec of the current draft."""
        from .workflow_plans import create

        report(lambda: create(home, change_name, path, note), "plan create", as_json)

    @plan.command("show")
    def plan_show(
        change_name: str = CHANGE,
        plan_id: str | None = typer.Option(None, "-p", "--plan", help="Plan number."),
        as_json: bool = JSON_OUTPUT,
        home: Path = HOME,
    ) -> None:
        """Show meta and spec of the open Plan, or of the given Plan."""
        from .workflow_plans import show

        report(lambda: show(home, change_name, plan_id), "plan show", as_json)

    @plan.command("list")
    def plan_list(
        change_name: str = CHANGE,
        as_json: bool = JSON_OUTPUT,
        home: Path = HOME,
    ) -> None:
        """List every Plan of the Change."""
        from .workflow_plans import plan_list as listing

        report(lambda: listing(home, change_name), "plan list", as_json)

    @plan.command("approve")
    def plan_approve(
        change_name: str = CHANGE,
        plan_id: str = PLAN,
        digest: str = typer.Option(..., "--digest", help="Digest the human confirmed."),
        path: str | None = typer.Option(None, "-f", "--file", help="Revision request file."),
        as_json: bool = JSON_OUTPUT,
        home: Path = HOME,
    ) -> None:
        """Confirm a draft Plan, or (with -f) a revision; only after a human confirmed it."""
        from .workflow_plans import approve

        report(lambda: approve(home, change_name, plan_id, digest, path), "plan approve", as_json)

    @plan.command("archive")
    def plan_archive(
        change_name: str = CHANGE,
        plan_id: str = PLAN,
        note: str | None = NOTE,
        as_json: bool = JSON_OUTPUT,
        home: Path = HOME,
    ) -> None:
        """Archive the draft or approved Plan; an approved one needs the human's consent first."""
        from .workflow_plans import archive

        report(lambda: archive(home, change_name, plan_id, note), "plan archive", as_json)

    @plan.command("rollback")
    def plan_rollback(
        change_name: str = CHANGE,
        plan_id: str = PLAN,
        as_json: bool = JSON_OUTPUT,
        home: Path = HOME,
    ) -> None:
        """Rework a failed Gate by its own on_fail; business code is never reverted."""
        from .workflow_plans import rollback

        report(lambda: rollback(home, change_name, plan_id), "plan rollback", as_json)

    # -------------------------------------------------------------------- node

    @node.command("instructions")
    def node_instructions(
        change_name: str = CHANGE,
        identity: str = NODE,
        as_json: bool = JSON_OUTPUT,
        home: Path = HOME,
    ) -> None:
        """Everything needed to execute one leaf node of the active Plan."""
        from .workflow_runtime import instructions
        from .workflow_state import open_change

        def action() -> dict:
            from .workflow_attempts import pending_sources, settled
            from .workflow_io import write_lock
            from .workflow_state import active_plan

            # Reading needs no lock, so parallel sub agents can start their nodes together;
            # only unfinished rework archiving must be completed (under the lock) first.
            ctx = open_change(home, change_name)
            loaded = active_plan(ctx)
            if not pending_sources(loaded):
                return instructions(loaded, identity)
            with write_lock(ctx.root):
                return instructions(settled(open_change(home, change_name)), identity)

        report(action, "node instructions", as_json)

    # ------------------------------------------------------------------- state

    @state.command("add")
    def state_add(
        change_name: str = CHANGE,
        section: str = typer.Option(..., "--section", help="Section key, e.g. decision."),
        text: str = typer.Option(..., "--text", help="One-line content of the record."),
        scope: str | None = typer.Option(
            None, "--scope", help="change or plan; required when the section exists in both."
        ),
        plan_id: str | None = typer.Option(
            None, "-p", "--plan", help="Plan number; defaults to the open Plan (plan scope only)."
        ),
        node: str | None = typer.Option(None, "-n", "--node", help="Leaf node or Gate id."),
        actor: str | None = typer.Option(
            None, "--actor", help="HUMAN or MODEL: who actually made the decision."
        ),
        by: str | None = typer.Option(
            None, "--by", help="The actual decision maker: the user or an Agent role."
        ),
        as_json: bool = JSON_OUTPUT,
        home: Path = HOME,
    ) -> None:
        """Append one record to the matching section of state.md (append only)."""
        from .workflow_state_notes import add

        report(
            lambda: add(
                home,
                change_name,
                section=section,
                text=text,
                scope=scope,
                plan=plan_id,
                node=node,
                actor=actor,
                by=by,
            ),
            "state add",
            as_json,
        )

    # -------------------------------------------------------------------- gate

    @gate.command("begin")
    def gate_begin(
        change_name: str = CHANGE,
        identity: str = NODE,
        as_json: bool = JSON_OUTPUT,
        home: Path = HOME,
    ) -> None:
        """Pin the code under review for a code Gate and get a one-time round id."""
        from .workflow_evidence import begin

        report(lambda: begin(home, change_name, identity), "gate begin", as_json)

    @gate.command("record")
    def gate_record(
        change_name: str = CHANGE,
        identity: str = NODE,
        round_id: str | None = typer.Option(None, "--round", help="Round id from gate begin."),
        report_path: str | None = typer.Option(None, "--report", help="Report under artifacts/."),
        as_json: bool = JSON_OUTPUT,
        home: Path = HOME,
    ) -> None:
        """Record a code Gate verdict, or run the system check of an assurance node."""
        from .workflow_evidence import record

        report(
            lambda: record(home, change_name, identity, round_id, report_path),
            "gate record",
            as_json,
        )

    # ---------------------------------------------------------------- fragment

    @fragment.command("list")
    def fragment_list(as_json: bool = JSON_OUTPUT, home: Path = HOME) -> None:
        def action() -> dict:
            catalog = WorkflowCatalog(home)
            version = catalog.registry_version()
            items = []
            for item in catalog.entries("fragments"):
                source = catalog.source("fragments", item.name)
                items.append(
                    {
                        **item.model_dump(by_alias=True),
                        "source": source,
                        "registry": version if source == "registry" else None,
                    }
                )
            return {"fragments": items}

        report(action, "fragment list", as_json)

    @fragment.command("show")
    def fragment_show(name: str, as_json: bool = JSON_OUTPUT, home: Path = HOME) -> None:
        report(
            lambda: WorkflowCatalog(home).fragment(name).model_dump(by_alias=True),
            "fragment show",
            as_json,
        )

    @fragment.command("validate")
    def fragment_validate(name: str, as_json: bool = JSON_OUTPUT, home: Path = HOME) -> None:
        def action() -> dict:
            expanded = FragmentExpander(WorkflowCatalog(home))
            expanded.expand(name, "fragment")
            expanded.connect()
            expanded.validate()
            expanded.resolve_nodes()
            return {"valid": True, "buildOrder": build_order(expanded.dependencies)}

        report(action, "fragment validate", as_json)

    # ----------------------------------------------------------------- profile

    @profile.command("list")
    def profile_list(as_json: bool = JSON_OUTPUT, home: Path = HOME) -> None:
        def action() -> dict:
            catalog = WorkflowCatalog(home)
            version = catalog.registry_version()
            items = []
            for item in catalog.entries("profiles"):
                source = catalog.source("profiles", item.name)
                items.append(
                    {
                        **item.model_dump(by_alias=True, exclude_none=True),
                        "source": source,
                        "registry": version if source == "registry" else None,
                    }
                )
            return {"profiles": items}

        report(action, "profile list", as_json)

    @profile.command("show")
    def profile_show(name: str, as_json: bool = JSON_OUTPUT, home: Path = HOME) -> None:
        report(
            lambda: (
                WorkflowCatalog(home).profile(name).model_dump(by_alias=True, exclude_none=True)
            ),
            "profile show",
            as_json,
        )

    @profile.command("validate")
    def profile_validate(name: str, as_json: bool = JSON_OUTPUT, home: Path = HOME) -> None:
        def action() -> dict:
            catalog = WorkflowCatalog(home)
            return validate_profile(catalog, catalog.profile(name))

        report(action, "profile validate", as_json)

    @profile.command("save")
    def profile_save(
        name: str,
        change_name: str = CHANGE,
        as_json: bool = JSON_OUTPUT,
        home: Path = HOME,
    ) -> None:
        """Save the active Plan's flow as a new Profile; never overwrites."""

        def action() -> dict:
            from contextlib import nullcontext

            from .registry_store import registry_spec
            from .registry_sync import registry_write_lock
            from .workflow_state import active_plan, open_change

            loaded = active_plan(open_change(home, change_name))
            profile = Profile(
                name=name,
                description="从需求 Plan 保存的工作流模板",
                flow=loaded.spec.flow,
            )
            guard = registry_write_lock(home) if registry_spec(home) else nullcontext()
            with guard:
                catalog = WorkflowCatalog(home)
                validate_profile(catalog, profile)
                path = "profiles/" + profile.name + ".yaml"
                if profile.name in catalog.registry_names("profiles"):
                    raise WorkflowError(
                        "profile_exists",
                        "registry 中已有同名 Profile，不会保存",
                        "换一个名称。",
                    )
                if exists(home, path):
                    raise WorkflowError(
                        "profile_exists", "同名 Profile 已存在，不会覆盖", "换一个名称。"
                    )
                write_yaml(
                    home,
                    path,
                    profile.model_dump(by_alias=True, exclude_none=True),
                    exclusive=True,
                )
            return {"saved": path, "includesRuntimeState": False}

        report(action, "profile save", as_json)

    # ------------------------------------------------------------------- graph

    @app.command("graph")
    def graph(
        profile_name: str | None = typer.Option(
            None, "--profile", help="Profile to draw (exclusive with --change)."
        ),
        change_name: str | None = typer.Option(
            None, "-c", "--change", help="Change whose Plan to draw (exclusive with --profile)."
        ),
        plan_id: str | None = typer.Option(
            None, "-p", "--plan", help="Plan number; defaults to the open Plan (needs --change)."
        ),
        output: Path | None = OUTPUT,
        no_open: bool = typer.Option(
            False, "--no-open", help="Only write the file and print its link."
        ),
        as_json: bool = typer.Option(False, "--json", help="Print the JSON payload instead."),
        home: Path = HOME,
    ) -> None:
        """Draw a Profile or Plan as an HTML dependency graph and open it in a browser."""
        from .workflow_graph import (
            REMOTE_REASONS,
            browser_decision,
            default_output,
            open_in_browser,
            plan_graph,
            profile_graph,
            write_graph,
        )
        from .workflow_graph_html import render_html

        def action() -> dict:
            if plan_id is not None and change_name is None:
                raise WorkflowError(
                    "option_conflict", "--plan 必须与 --change 一起使用", "加上 -c <change>。"
                )
            if (profile_name is None) == (change_name is None):
                raise WorkflowError(
                    "option_conflict",
                    "--profile 与 --change 必须且只能指定一个",
                    "loopspec graph --profile <name> 或 loopspec graph -c <change> [--plan <id>]",
                )
            if profile_name is not None:
                drawn = profile_graph(home, profile_name)
                target = {"profile": profile_name}
            else:
                assert change_name is not None
                drawn = plan_graph(home, change_name, plan_id)
                target = {"change": change_name, "plan": drawn.meta["Plan"]}
            relative = default_output(
                drawn.kind, target.get("change"), target.get("plan"), target.get("profile")
            )
            path = write_graph(home, render_html(drawn), relative, output)
            url = path.as_uri()
            should_open, reason = browser_decision(no_open)
            opened = False
            if should_open:
                opened, reason = open_in_browser(url)
            return {
                "kind": drawn.kind,
                "target": target,
                "path": str(path),
                "url": url,
                "opened": opened,
                "reason": reason,
                "nodes": len(drawn.nodes),
                "layers": len(drawn.layers),
                "parallelLayers": drawn.parallel_layers,
            }

        def render(result: dict) -> str:
            lines = [f"Graph written: {result['path']}", f"URL: {result['url']}"]
            parallel = result["parallelLayers"]
            lines.append(
                f"{result['nodes']} nodes, {result['layers']} layers; parallel layers: "
                + (", ".join(f"L{n}" for n in parallel) if parallel else "none")
            )
            if result["opened"]:
                lines.append("Opened in your browser.")
            else:
                lines.append(f"Not opened ({result['reason']}).")
                if result["reason"] in REMOTE_REASONS:
                    lines.append(
                        f"Copy it to a machine with a browser, e.g. scp <host>:{result['path']} ."
                    )
                else:
                    lines.append("Open the URL above in a browser.")
            return "\n".join(lines) + "\n"

        def render_error(error: dict) -> str:
            text = f"Error [{error['error']}]: {error['message']}\n"
            return text + (f"Fix: {error['fix']}\n" if error.get("fix") else "")

        if as_json:
            run(action)
        else:
            run(action, render, render_error)

    # ---------------------------------------------------------------- registry

    @registry.command("update")
    def registry_update(full: bool = FULL, as_json: bool = JSON_OUTPUT, home: Path = HOME) -> None:
        """Fetch the registry and plan an update of registry.lock.yaml; never writes the lock."""
        from .registry_sync import update

        report(lambda: update(home, full=full), "registry update", as_json)

    @registry.command("apply")
    def registry_apply(
        plan_id: str = REGISTRY_PLAN,
        as_json: bool = JSON_OUTPUT,
        home: Path = HOME,
    ) -> None:
        """Apply a confirmed plan: verify the global snapshot and update registry.lock.yaml."""
        from .registry_sync import apply

        report(lambda: apply(home, plan_id), "registry apply", as_json)
