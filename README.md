# LoopSpec

A gated artifact workflow CLI for LLM-driven, spec-driven development. You declare a
YAML graph of artifacts (proposal, specs, design, tasks, ...) and their dependencies;
an LLM generates them one at a time; special *gate* nodes (e.g. a security review)
produce a PASS/FAIL verdict, and a FAIL rolls back to a declared upstream node so the
LLM can redo it with full knowledge of why the previous attempt failed.

Node completion, gate verdicts, and retry counts are all derived from the filesystem
on every call — there is no separate progress database to drift out of sync with
what's actually on disk. Rollbacks *move* (never delete) prior attempts into
`.attempts/round-NNN/`, so the next attempt can be shown exactly what failed and why.

## Install

```bash
curl -fsSL https://raw.githubusercontent.com/mingyuans/LoopSpec/main/install.sh | sh
```

The same command installs and updates — re-run it to move to the latest release. It
downloads the wheel from the newest GitHub Release, verifies its SHA256 against the
release's `checksums.txt`, and installs it with `uv tool install` (or `pipx install`
if you don't have uv). Nothing needs `sudo`, and there is no flag to skip the
checksum check.

If you'd rather read the script before running it:

```bash
curl -fsSLO https://raw.githubusercontent.com/mingyuans/LoopSpec/main/install.sh
less install.sh
sh install.sh
```

Pin a specific version with `LOOPSPEC_VERSION`:

```bash
curl -fsSL https://raw.githubusercontent.com/mingyuans/LoopSpec/main/install.sh \
  | LOOPSPEC_VERSION=0.1.0 sh
```

### Without the script

The wheel is a normal `py3-none-any` wheel, so any tool that installs CLI apps works:

```bash
uv tool install https://github.com/mingyuans/LoopSpec/releases/latest/download/loopspec-0.1.0-py3-none-any.whl
# or
pipx install https://github.com/mingyuans/LoopSpec/releases/latest/download/loopspec-0.1.0-py3-none-any.whl
```

Substitute the version you want; the filenames are listed on each release page. Note
that this path skips the checksum verification the script does for you.

**Windows:** use `uv tool install` directly — `install.sh` is POSIX shell and there is
no PowerShell equivalent.

### Update and uninstall

```bash
# update: the same command as installing
curl -fsSL https://raw.githubusercontent.com/mingyuans/LoopSpec/main/install.sh | sh

# uninstall
uv tool uninstall loopspec     # or: pipx uninstall loopspec
```

If `loopspec` isn't found after installing, the tool directory (usually
`~/.local/bin`) isn't on your `PATH` yet — run `uv tool update-shell` (or
`pipx ensurepath`) and restart your shell.

## Releases

Publishing is driven by tags, not by commits. Pushing to `main` runs the checks and
builds; it never creates a release. To publish:

```bash
# 1. set the version in BOTH places, and merge that to main
#      pyproject.toml        -> project.version
#      src/loopspec/__init__.py -> __version__
# 2. tag a commit on main
git tag v0.2.0
# 3. push the tag -- this is what publishes
git push origin v0.2.0
```

The release version comes from the tag name. CI requires the tag to agree with both
version declarations and fails before building if it doesn't — the wheel's filename
comes from `pyproject.toml`, so a mismatch would otherwise produce a release whose
assets are named after a different version. It also requires the tagged commit to be
reachable from `main`, and refuses to overwrite an existing release for the same tag.

`make release-dry-run TAG=v0.2.0` runs the checks that don't need CI, so you can catch
a version mismatch before spending a tag on it.

Each release carries three assets:

- `loopspec-<version>-py3-none-any.whl`
- `loopspec-<version>.tar.gz`
- `checksums.txt` — SHA256 of the two above, which `install.sh` verifies

Two things to know before the first release:

- **Repository setting.** `Settings → Actions → General → Workflow permissions` must
  allow *Read and write*, otherwise creating the release fails with a 403.
- **Anyone who can push a `v*` tag can publish.** The workflow constrains *what* can
  be released (a commit on `main`, declaring the version the tag names, not already
  released) but not *who* may release it. If that matters for your fork, restrict tag
  pushes with a repository ruleset — that's a repository setting, not something this
  workflow enforces.

## Quick start

```bash
# 1. Initialize a workflow home (copies the built-in `secure-spec-driven` schema)
loopspec init ./loopspec

# 1b. Optionally scaffold AI-tool skills/commands (/lpsx:new, /lpsx:continue,
#     /lpsx:archive, /lpsx:bulk-archive) for the tools you use. 31 tools are
#     supported — run `loopspec init` in a terminal to browse them.
loopspec init ./loopspec --tools claude,codex
#   -> writes .claude/skills/loopspec-*/SKILL.md + .claude/commands/lpsx/*.md
#      and .codex/skills/loopspec-*/SKILL.md + a global ~/.codex/prompts/lpsx-*.md
# These land in your *project root* (the parent of the workflow home), because
# that's where AI tools look for .claude/.codex — override with --project-root.
# Use --tools all for every supported tool, or omit --tools in an interactive
# terminal to pick from a searchable list (see below). Non-interactively,
# omitting --tools is equivalent to --tools none (no tool scaffolding).

# 2. Create a change
loopspec new add-payment --home ./loopspec --json

# 3. Ask what to do next
loopspec status add-payment --home ./loopspec --json
#   -> nextSteps tells you to run `loopspec instructions <node> --change ...`

# 4. Get the instructions for the next node, write the artifact it describes,
#    then go back to step 3.
loopspec instructions proposal --change add-payment --home ./loopspec --json

# If a gate fails, `status` returns a `pendingRollback` command:
loopspec rollback add-payment --home ./loopspec --json
# ...then redo the reset nodes; `instructions` will include `priorAttempts`
# with the previous failure's blocking issues so you don't repeat them.

# Once everything is done:
loopspec archive add-payment --home ./loopspec --json
```

Every command supports `--json` for machine-readable output — that's the primary
protocol for driving `loopspec` from an LLM/agent. Omit `--json` for a plain-text
summary intended for humans. `init` looks like this:

```
$ loopspec init ./loopspec --tools claude,codex
▌ Workflow home ready at loopspec
✔ Setup complete for Claude Code
✔ Setup complete for Codex

LoopSpec Setup Complete

Created: Claude Code, Codex
8 skills and 8 commands in .claude, .codex

Config: loopspec/config.yaml (schema: secure-spec-driven)

Getting started:
  loopspec new <change-name>

Learn more: https://github.com/mingyuans/LoopSpec
Feedback:   https://github.com/mingyuans/LoopSpec/issues

Restart your IDE for slash commands to take effect.
```

Re-running it reports the same tools under `Refreshed:` instead of `Created:`. The
summary aggregates on purpose — the full list of written paths stays in `--json`
under `scaffoldedFiles`. Colour and the spinner drop out automatically when the
output isn't a terminal or `NO_COLOR` is set, and the glyphs fall back to ASCII
(`ok`/`x`/`!`/`-`/`|`) when the output encoding can't represent them.

### Picking tools interactively

Run `loopspec init` in a terminal without `--tools` and it opens with a welcome
screen, then a searchable multi-select over all 31 supported tools:

```
$ loopspec init ./loopspec

█    ▄▀▀▄ ▄▀▀▄ █▀▀▄ ▄▀▀▀ █▀▀▄ █▀▀▀ ▄▀▀▀
█    █  █ █  █ █▀▀  ▀▀▀▄ █▀▀  █▀▀  █
▀▀▀▀ ▀▄▄▀ ▀▄▄▀ █    ▄▄▄▀ █    ▀▀▀▀ ▀▄▄▄

Welcome to LoopSpec
A gated artifact workflow for spec-driven development

This setup will configure:
  • Agent Skills for AI tools
  • /lpsx:* slash commands

Quick start after setup:
  /lpsx:new       Create a change
  /lpsx:continue  Advance to the next artifact
  /lpsx:archive   Archive a finished change

Press Enter to select tools...

Detected tool directories: Claude Code (pre-selected for first-time setup)
? Select tools to set up (31 available)
  ↑↓ navigate • Space toggle • type to filter • Enter confirm
❯ ◉ Claude Code (detected)
  ○ Amazon Q Developer
  ○ Antigravity
  ...
```

Type to filter by display name, Space to toggle, Enter to confirm. Confirming
with nothing checked is the same as `--tools none`, and Ctrl+C is treated as
"configure nothing this run" rather than an error.

On a **first-time** setup the tools whose directories are already on disk start
checked. Once anything is configured, later runs pre-select what is *configured*
instead — so re-running `init` defaults to refreshing the tools you already set
up rather than quietly adding every editor you've installed since. (`.github/`
is checked for specific Copilot files rather than mere existence, since nearly
every repository has that directory.)

**Three cases never show any of this:** `--json`, an explicit `--tools` (including
`all`/`none`), and a non-interactive stdin/stdout (pipes, redirects, CI). In the
last case, omitting `--tools` stays equivalent to `--tools none`.

## Two nodes that aren't just "write a file"

The built-in schema's last two nodes ask the agent for something other than
another document, so a driving loop needs to expect them:

- **`approval` — a human sign-off gate.** The agent summarizes every artifact
  produced so far and asks *you* to decide, using its host tool's interactive
  question facility (Claude Code's `AskUserQuestion`, or the equivalent). You
  approve → `approval/approved.md`; you ask for changes → 
  `approval/changes-requested.md`, which rolls the change back and redoes
  `specs`/`design`/`tasks` with your requests attached as `priorAttempts`. The
  agent is told never to approve on your behalf: with no way to reach a human,
  the node simply stays `ready` and waits. Either way the verdict is recorded in
  `state.md` — distilled and de-pronouned, with your verbatim words kept in the
  verdict file.
- **`apply` — the implementation gate.** The agent reads every artifact
  (`contextFiles` in the `instructions` response hands it the real paths), works
  through `tasks.md` ticking checkboxes as it goes, runs the project's tests, and
  writes `apply/report.md`. It declares `apply/blocked.md` instead if the plan
  itself turns out to be unworkable, which rolls back to `design`.

`apply` declares `tracks: tasks.md`, and a node with `tracks` is only `done` once
every checkbox in the tracked file is ticked — so writing the report early leaves
the node `ready` and `loopspec archive` keeps refusing. `loopspec status` reports
`taskProgress` counts per tracked node; `loopspec instructions` adds the per-task
list.

## Development

```bash
make install          # uv sync -- package + dev tools (pytest, ruff, mypy) into .venv
make test             # uv run pytest -v
make lint             # ruff check + mypy
make build            # uv build
make release-dry-run  # version check + install.sh checks + build
make clean            # remove build/test caches
```

`make release-dry-run` accepts `TAG=v0.2.0` to also verify a tag name against the two
version declarations. It skips `shellcheck` when it isn't installed locally; CI treats
it as mandatory.

The built-in `secure-spec-driven` schema lives in `schemas/secure-spec-driven/` at
the repo root and is bundled into the installed package (see
`schemas/secure-spec-driven/schema.yaml` for its node graph: `proposal` →
`{specs, design}` → `tasks` → `security` gate → `approval` gate (human sign-off)
→ `apply` gate (implementation, `tracks: tasks.md`)).
