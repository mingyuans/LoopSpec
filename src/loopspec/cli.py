"""loopspec CLI: `version`, `init`, and the `loopspec <resource> <verb>` workflow tree."""

from __future__ import annotations

import json
import sys
from functools import partial
from pathlib import Path
from typing import NoReturn

import typer

from . import self_update, workflow_cli
from .errors import LoopspecError
from .plan_guard import MAX_HOOK_INPUT, hook_output
from .presentation import Presenter, render_init_summary, render_welcome
from .scaffold import ScaffoldResult, install_hooks, scaffold_tools
from .tool_registry import AI_TOOLS
from .tools_cli import is_interactive, pick_tools, resolve_tools_arg

app = typer.Typer(help="loopspec: a gated, plan-driven workflow CLI.", no_args_is_help=True)
workflow_cli.register(app)
hook_app = typer.Typer(help="Agent hooks that guard LoopSpec files.", no_args_is_help=True)
app.add_typer(hook_app, name="hook")

DEFAULT_HOME = Path("./loopspec")

JsonOption = typer.Option(False, "--json", help="Emit machine-readable JSON.")
HomePathArgument = typer.Argument(DEFAULT_HOME)
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
UpdateResourcesOption = typer.Option(
    False,
    "--update-resources",
    help=(
        "Copy missing built-in fragments/profiles even when the workflow home "
        "already has some, without asking."
    ),
)
PROJECT_URL = "https://github.com/mingyuans/LoopSpec"
ISSUES_URL = f"{PROJECT_URL}/issues"
DEFAULT_CONFIG = "artifacts_dir: changes\nworkflow: {}\n"


def _fail(exc: LoopspecError, as_json: bool) -> NoReturn:
    payload = exc.to_dict()
    if as_json:
        typer.echo(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        typer.echo(f"Error [{payload['error']}]: {payload['message']}")
        if payload["fix"]:
            typer.echo(f"Fix: {payload['fix']}")
    raise typer.Exit(code=1)


@app.command()
def version(as_json: bool = JsonOption) -> None:
    """Print the installed loopspec version."""

    from . import __version__ as installed_version

    if as_json:
        typer.echo(json.dumps({"version": installed_version}))
    else:
        typer.echo(installed_version)


VersionOption = typer.Option(
    None, "--version", help="Install this exact release instead of the latest one."
)
CheckOption = typer.Option(
    False, "--check", help="Only report whether a newer release exists; install nothing."
)


@app.command()
def update(
    version: str | None = VersionOption,
    check: bool = CheckOption,
    as_json: bool = JsonOption,
) -> None:
    """Update the loopspec CLI to the latest (or a pinned) release."""

    from . import __version__ as installed_version

    # In JSON mode stdout carries exactly one JSON document, so the installer's
    # own progress output is sent to stderr instead.
    run = (
        partial(self_update.default_runner, stdout=sys.stderr)
        if as_json
        else self_update.default_runner
    )
    try:
        result = self_update.run_update(
            installed_version,
            version=version,
            check=check,
            run=run,
            on_download=None if as_json else _announce_download,
        )
    except LoopspecError as exc:
        _fail(exc, as_json)

    if as_json:
        typer.echo(json.dumps(result.to_dict()))
    elif result.status == "up_to_date":
        typer.echo(f"loopspec {result.current} is up to date.")
    elif result.status == "available":
        command = "loopspec update" + ("" if version is None else f" --version {version}")
        typer.echo(
            f"loopspec {result.latest} is available (installed: {result.current}). "
            f"Run `{command}` to install it."
        )
    else:
        typer.echo(f"Updated loopspec {result.current} -> {result.latest} with {result.installer}.")


def _announce_download(version: str) -> None:
    typer.echo(f"Downloading loopspec {version}...")


@hook_app.command("pre-tool-use")
def pre_tool_use() -> None:
    """Claude Code / Codex PreToolUse hook: deny direct edits of an approved plan.yaml."""

    # Read one character past the limit so hook_output can tell the input was cut short.
    output = hook_output(typer.get_text_stream("stdin").read(MAX_HOOK_INPUT + 1))
    if output:
        typer.echo(output)


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


def _welcome_and_pick(presenter: Presenter, scaffold_root: Path) -> list[str]:
    """The interactive tool-selection path: welcome screen, then the picker.

    Deliberately one function rather than two calls at the call site, so no
    future edit can render the welcome screen without the picker it promises
    (design D3).
    """

    render_welcome(presenter)
    input()  # honours the welcome screen's own "Press Enter to select tools..."
    return pick_tools(scaffold_root)


def _confirm_resource_update(presenter: Presenter) -> bool:
    """Ask before touching an existing catalog; anything but yes keeps it."""

    presenter.line(
        presenter.warning("fragments/ or profiles/ already exist in the workflow home.")
    )
    try:
        answer = input("Copy missing built-in fragments/profiles into them? [y/N] ")
    except EOFError:
        return False
    return answer.strip().lower() in {"y", "yes"}


def _init_counts(result: ScaffoldResult) -> tuple[int, int]:
    written = [path for paths in result.written_files.values() for path in paths]
    skills = sum(1 for path in written if path.endswith("SKILL.md"))
    return skills, len(written) - skills


@app.command()
def init(
    path: Path = HomePathArgument,
    tools: str | None = ToolsOption,
    project_root: Path | None = ProjectRootOption,
    update_resources: bool = UpdateResourcesOption,
    as_json: bool = JsonOption,
) -> None:
    """Initialize a workflow home."""

    presenter = None if as_json else Presenter()

    path.mkdir(parents=True, exist_ok=True)
    (path / "changes").mkdir(exist_ok=True)

    config_path = path / "config.yaml"
    created_files = []
    if not config_path.is_file():
        config_path.write_text(DEFAULT_CONFIG, encoding="utf-8")
        created_files.append("config.yaml")

    from .workflow_resources import install_resources, resources_present

    # An existing catalog may be hand-tuned or registry-synced; re-running init
    # to refresh skills must not quietly re-add built-ins the user removed.
    install = update_resources or not resources_present(path)
    if not install and presenter is not None and is_interactive():
        install = _confirm_resource_update(presenter)

    copied_workflows: list[str] = []
    if install:
        try:
            copied_workflows = install_resources(path)
        except LoopspecError as exc:
            _fail(exc, as_json)
    elif presenter is not None:
        presenter.line(
            presenter.dim(
                "Kept existing fragments/profiles; "
                "rerun with --update-resources to add missing built-ins."
            )
        )

    if presenter is not None:
        presenter.line(presenter.ready(f"Workflow home ready at {_display_path(path)}"))

    # AI tools look for `.claude/`, `.codex/`, ... at the *project* root, not
    # inside the workflow home, so scaffold into the workflow home's parent
    # unless the caller pointed us somewhere else explicitly. Resolved before the
    # prompt so the tool list can report each tool's current state there.
    scaffold_root = (project_root or path.resolve().parent).resolve()

    try:
        # One condition decides the welcome screen *and* the picker together --
        # `_welcome_and_pick` is the only caller of either, so they cannot come
        # apart. The screen signs off with "Press Enter to select tools...", and
        # showing that without a picker behind it tells the user to press Enter
        # for nothing (design D3). `presenter is not None` is exactly `not
        # as_json`; spelling it this way keeps the narrowing for free.
        if tools is None and presenter is not None and is_interactive():
            tool_ids = _welcome_and_pick(presenter, scaffold_root)
        elif tools is None:
            tool_ids = []
        else:
            tool_ids = resolve_tools_arg(tools)
    except LoopspecError as exc:
        _fail(exc, as_json)

    scaffold_result = _scaffold_with_progress(scaffold_root, tool_ids, presenter)
    hooks = install_hooks(scaffold_root, tool_ids)

    result = {
        "workflowHome": str(path.resolve()),
        "projectRoot": str(scaffold_root),
        "createdFiles": created_files,
        "copiedWorkflowResources": copied_workflows,
        "resourcesUpdate": "installed" if install else "skipped",
        "toolsConfigured": tool_ids,
        "scaffoldedFiles": scaffold_result.written_files,
        "skippedCommandGeneration": scaffold_result.skipped_command_generation,
        "createdTools": scaffold_result.created,
        "refreshedTools": scaffold_result.refreshed,
        "hooks": hooks,
        "nextSteps": [f"loopspec change new <change-name> --home {path}"],
    }

    if presenter is None:
        typer.echo(json.dumps(result, ensure_ascii=False, indent=2, default=str))
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
        config_created="config.yaml" in created_files,
        getting_started=f"loopspec change new <change-name>{home_suffix}",
        project_url=PROJECT_URL,
        issues_url=ISSUES_URL,
    )
    _render_hooks(presenter, hooks)


def _render_hooks(presenter: Presenter, hooks: dict[str, dict]) -> None:
    for tool_id, hook in hooks.items():
        label = AI_TOOLS[tool_id].label
        where = _display_path(Path(hook["path"]))
        if hook["status"] == "skipped":
            presenter.line(
                presenter.warning(f"{label} plan guard hook not added to {where}: {hook['reason']}")
            )
            continue
        presenter.line(presenter.success(f"{label} plan guard hook {hook['status']}: {where}"))
        if tool_id == "codex":
            presenter.line(
                presenter.dim("Review and trust it in Codex with /hooks before it runs.")
            )
