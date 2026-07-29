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
make install
```

This runs `uv sync`, installing the `loopspec` package and its dependencies (including
dev tools: `pytest`, `ruff`, `mypy`) into a local virtualenv.

## Quick start

```bash
# 1. Initialize a workflow home (copies the built-in `secure-spec-driven` schema)
loopspec init ./loopspec

# 1b. Optionally scaffold AI-tool skills/commands (/lpsx:new, /lpsx:continue,
#     /lpsx:archive, /lpsx:bulk-archive) for the tools you use. Supported ids:
#     claude, codex, opencode, cursor, windsurf.
loopspec init ./loopspec --tools claude,codex
#   -> writes .claude/skills/loopspec-*/SKILL.md + .claude/commands/lpsx/*.md
#      and .codex/skills/loopspec-*/SKILL.md + a global ~/.codex/prompts/lpsx-*.md
# These land in your *project root* (the parent of the workflow home), because
# that's where AI tools look for .claude/.codex — override with --project-root.
# Use --tools all for every supported tool, or omit --tools in an interactive
# terminal to get a numbered prompt instead. Non-interactively, omitting
# --tools is equivalent to --tools none (no tool scaffolding).

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
make test    # uv run pytest -v
make lint    # ruff check + mypy
make build   # uv build
make clean   # remove build/test caches
```

The built-in `secure-spec-driven` schema lives in `schemas/secure-spec-driven/` at
the repo root and is bundled into the installed package (see
`schemas/secure-spec-driven/schema.yaml` for its node graph: `proposal` →
`{specs, design}` → `tasks` → `security` gate → `approval` gate (human sign-off)
→ `apply` gate (implementation, `tracks: tasks.md`)).
