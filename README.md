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
summary intended for humans.

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
`{specs, design}` → `tasks` → `security` gate).
