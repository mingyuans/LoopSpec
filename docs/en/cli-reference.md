# CLI reference

> Scope: every `loopspec` command — purpose, syntax, options, `--json` response fields, worked examples — plus the error code table.
> Audience: humans looking up a flag, and LLM agents that need the exact response shape.
> Language: **English** · [中文](../zh/cli-reference.md)

Every command accepts `--json`. That is the primary protocol for driving LoopSpec from an agent; without it you get a plain-text summary meant for a person. Both modes present the same facts, but the human-readable mode is allowed to aggregate (counts instead of full path lists).

Two options recur on nearly every command:

| Option | Type | Default | Description |
| --- | --- | --- | --- |
| `--home` | path | `./loopspec` | The workflow home to operate on. See [workflow home](overview.md#glossary). |
| `--json` | flag | off | Emit machine-readable JSON on stdout instead of the human summary. |

All JSON paths in the examples below are shown rooted at `/path/to/project` — real output contains absolute paths on your machine.

## Failure contract

Every command that fails exits with code **1** and, in `--json` mode, prints an object with exactly three fields:

| Field | Type | Description |
| --- | --- | --- |
| `error` | string | Machine-readable error code, from the [error code table](#error-codes). |
| `message` | string | Human-readable explanation of what went wrong. |
| `fix` | string | Suggested next action. May be an empty string when no specific fix applies. |

```json
{
  "error": "change_not_found",
  "message": "Change not found: nope",
  "fix": ""
}
```

A successful command exits with code **0**.

## loopspec version

Print the installed LoopSpec version.

```bash
loopspec version [--json]
```

| Option | Type | Default | Description |
| --- | --- | --- | --- |
| `--json` | flag | off | Emit `{"version": "..."}` instead of the bare version string. |

| Field | Type | Description |
| --- | --- | --- |
| `version` | string | Installed package version, stamped from the git tag it was built from. `0.0.0.dev0` in a source tree that was never installed, since there is no release version to report. |

```json
{"version": "0.1.0"}
```

## loopspec init

Create a workflow home, copy the built-in schemas into it, and optionally scaffold skill and slash-command files for AI coding tools.

```bash
loopspec init [PATH] [--no-builtin] [--tools all|none|<ids>] [--project-root <dir>] [--json]
```

| Option | Type | Default | Description |
| --- | --- | --- | --- |
| `PATH` | path | `./loopspec` | Positional argument: where to create the workflow home. |
| `--no-builtin` | flag | off | Skip copying the bundled built-in schemas. |
| `--tools` | string | see below | `all`, `none`, or a comma-separated list of tool ids (for example `claude,codex`). |
| `--project-root` | path | parent of `PATH` | Where to write tool directories such as `.claude` and `.codex`. |
| `--json` | flag | off | Emit machine-readable JSON and suppress all progress output and decoration. |

`init` is idempotent: an existing `config.yaml` is left alone, and a schema directory that already exists is not overwritten. Re-running it refreshes tool scaffolding rather than duplicating it.

### How `--tools` resolves

- Explicit value (`all`, `none`, or a list) is always honoured.
- Omitted, in an interactive terminal, without `--json`: a welcome screen and a searchable multi-select over all 31 registered tools. On a first-time setup the tools whose directories are already present start checked; once anything is configured, later runs pre-select what is *configured* instead. Confirming with nothing checked equals `none`, and Ctrl+C is treated as "configure nothing this run" rather than an error.
- Omitted, non-interactively (pipes, redirects, CI) or with `--json`: equivalent to `none`.

Skill files are written to `<project root>/<tool dir>/skills/loopspec-*/SKILL.md` for every selected tool. Slash commands are written only for tools that have a command adapter; 28 of the 31 registered tools do, and the three that do not (`forgecode`, `kimi`, `vibe`) are reported in `skippedCommandGeneration`.

| Field | Type | Description |
| --- | --- | --- |
| `workflowHome` | string | Absolute path of the workflow home that now exists. |
| `projectRoot` | string | Absolute path the tool directories were written under. |
| `createdFiles` | array of string | Workflow-home files created by this run; empty when everything already existed. |
| `copiedSchemas` | array of string | Built-in schema names copied in by this run. |
| `toolsConfigured` | array of string | Tool ids selected for this run. |
| `scaffoldedFiles` | object | Tool id to the list of files written for it. |
| `skippedCommandGeneration` | array of string | Tool ids that got skills but no slash commands, because no command adapter exists for them. |
| `createdTools` | array of string | Tool ids configured for the first time. |
| `refreshedTools` | array of string | Tool ids that already had skill files and were rewritten. |
| `nextSteps` | array of string | Suggested follow-up commands. |

```json
{
  "workflowHome": "/path/to/project/loopspec",
  "projectRoot": "/path/to/project",
  "createdFiles": [
    "config.yaml"
  ],
  "copiedSchemas": [
    "secure-spec-driven"
  ],
  "toolsConfigured": [],
  "scaffoldedFiles": {},
  "skippedCommandGeneration": [],
  "createdTools": [],
  "refreshedTools": [],
  "nextSteps": [
    "Run `loopspec schemas list --home /path/to/project/loopspec --json` to see available schemas."
  ]
}
```

Without `--json`, `init` prints a sectioned summary: a `Created:` or `Refreshed:` tool list, an aggregate count line, the config path and its schema, any skipped command generation, a `Getting started:` command, and documentation links. Colour and the progress spinner drop out automatically when stdout is not a terminal or `NO_COLOR` is set, and the Unicode glyphs fall back to ASCII (`ok`, `x`, `!`, `-`, `|`) when the output encoding cannot represent them.

## loopspec schemas list

List every loadable schema in the workflow home.

```bash
loopspec schemas list [--home <dir>] [--json]
```

| Option | Type | Default | Description |
| --- | --- | --- | --- |
| `--home` | path | `./loopspec` | Workflow home to scan. |
| `--json` | flag | off | Emit machine-readable JSON. |

A directory under `<home>/schemas/` without a `schema.yaml`, or with one that fails to load, is skipped silently rather than failing the whole listing.

| Field | Type | Description |
| --- | --- | --- |
| `schemas` | array of object | One entry per loadable schema. |
| `schemas[].name` | string | Schema name as declared inside `schema.yaml`. |
| `schemas[].version` | integer | Schema version. |
| `schemas[].source` | string | Always `local` in this release. |
| `schemas[].path` | string | Absolute path of the schema directory. |
| `schemas[].nodes` | array of string | Node ids in topological order. |

```json
{
  "schemas": [
    {
      "name": "secure-spec-driven",
      "version": 1,
      "source": "local",
      "path": "/path/to/project/loopspec/schemas/secure-spec-driven",
      "nodes": [
        "proposal",
        "specs",
        "design",
        "tasks",
        "security",
        "approval",
        "apply"
      ]
    }
  ]
}
```

## loopspec schemas show

Show one schema's node graph.

```bash
loopspec schemas show <name> [--home <dir>] [--json]
```

| Option | Type | Default | Description |
| --- | --- | --- | --- |
| `NAME` | string | required | Positional argument: schema directory name under `<home>/schemas/`. |
| `--home` | path | `./loopspec` | Workflow home to read from. |
| `--json` | flag | off | Emit machine-readable JSON. |

| Field | Type | Description |
| --- | --- | --- |
| `name` | string | Schema name. |
| `version` | integer | Schema version. |
| `nodes` | array of object | Nodes in build (topological) order. |
| `nodes[].id` | string | Node id. |
| `nodes[].requires` | array of string | Node ids this node depends on. |
| `nodes[].generates` | string or null | Artifact path or glob; `null` for gates that produce no document. |
| `nodes[].isGate` | boolean | Whether the node declares a `gate` block. |

```json
{
  "name": "secure-spec-driven",
  "version": 1,
  "nodes": [
    {
      "id": "proposal",
      "requires": [],
      "generates": "proposal.md",
      "isGate": false
    },
    {
      "id": "security",
      "requires": [
        "tasks"
      ],
      "generates": null,
      "isGate": true
    }
  ]
}
```

Fails with `schema_not_found` when no `schema.yaml` exists at that path, or `schema_invalid` when it exists but does not validate.

## loopspec schemas validate

Load a schema and run every structural and semantic check against it.

```bash
loopspec schemas validate <name> [--home <dir>] [--json]
```

| Option | Type | Default | Description |
| --- | --- | --- | --- |
| `NAME` | string | required | Positional argument: schema directory name under `<home>/schemas/`. |
| `--home` | path | `./loopspec` | Workflow home to read from. |
| `--json` | flag | off | Emit machine-readable JSON. |

| Field | Type | Description |
| --- | --- | --- |
| `valid` | boolean | Always `true` — an invalid schema exits 1 with an error object instead. |
| `name` | string | Schema name. |
| `buildOrder` | array of string | Node ids in topological order, with ties broken by id so the order is stable across runs. |

```json
{
  "valid": true,
  "name": "secure-spec-driven",
  "buildOrder": [
    "proposal",
    "design",
    "specs",
    "tasks",
    "security",
    "approval",
    "apply"
  ]
}
```

This is the command to use while authoring a schema. See [Schema reference](schema-reference.md) for the full list of checks and the error code each one raises.

```json
{
  "error": "schema_invalid",
  "message": "Cyclic dependency: alpha → beta → alpha",
  "fix": "Remove the circular `requires` reference between these nodes."
}
```

## loopspec new

Create a change directory, record which schema it uses, and write its initial `state.md`.

```bash
loopspec new <change-name> [--schema <name>] [--home <dir>] [--json]
```

| Option | Type | Default | Description |
| --- | --- | --- | --- |
| `CHANGE_NAME` | string | required | Positional argument: kebab-case change name (`^[a-z][a-z0-9]*(-[a-z0-9]+)*$`). |
| `--schema` | string | from config | Which schema to use. Required when `config.yaml` lists more than one candidate. |
| `--home` | path | `./loopspec` | Workflow home to create the change in. |
| `--json` | flag | off | Emit machine-readable JSON. |

The chosen schema is written to the change's `.workflow.yaml`, so later commands operate on the same schema even if the project default changes. See [Configuration](configuration.md) for the full resolution order.

| Field | Type | Description |
| --- | --- | --- |
| `changeName` | string | The change's name. |
| `schemaName` | string | Schema resolved for this change. |
| `artifactsDir` | string | Value of `artifacts_dir` from `config.yaml`. |
| `schemaPath` | string or null | The schema reference's `path`, when the schema nests artifacts in a subdirectory. |
| `changeRoot` | string | Absolute path of the change directory. |
| `artifactRoot` | string | Absolute path artifacts are resolved against. Equals `changeRoot` unless `schemaPath` is set. |
| `statePath` | string | Absolute path of the change's `state.md`. |
| `metadataPath` | string | Absolute path of the change's `.workflow.yaml`. |
| `created` | string | Creation date, `YYYY-MM-DD`. |
| `createdFiles` | array of string | Files written by this command. |
| `nextSteps` | array of string | Suggested follow-up commands. |

```json
{
  "changeName": "add-payment",
  "schemaName": "secure-spec-driven",
  "artifactsDir": "changes",
  "schemaPath": null,
  "changeRoot": "/path/to/project/loopspec/changes/add-payment",
  "artifactRoot": "/path/to/project/loopspec/changes/add-payment",
  "statePath": "/path/to/project/loopspec/changes/add-payment/state.md",
  "metadataPath": "/path/to/project/loopspec/changes/add-payment/.workflow.yaml",
  "created": "2026-07-29",
  "createdFiles": [
    ".workflow.yaml",
    "state.md"
  ],
  "nextSteps": [
    "Run `loopspec status add-payment --json` to see the first node."
  ]
}
```

When `config.yaml` lists several candidate schemas and `--schema` was not given, the command exits 1 with `schema_selection_required` and, unusually for an error, includes the candidate list so a caller can present the choice:

```json
{
  "error": "schema_selection_required",
  "message": "config.yaml defines multiple candidate schemas; one must be chosen before creating this change.",
  "fix": "Pick a schemas[*].name and re-run with --schema <name>.",
  "changeName": "some-change",
  "artifactsDir": "changes",
  "schemas": [
    {
      "name": "secure-spec-driven",
      "path": null,
      "description": "Full spec-driven flow with security, approval and implementation gates",
      "when": "Default choice for anything that touches production behaviour"
    },
    {
      "name": "docs-only",
      "path": null,
      "description": "Lightweight flow for documentation-only changes",
      "when": "Use when no runtime code changes"
    }
  ],
  "selectionInstruction": "Ask the human which flow fits before creating the change."
}
```

Other failures: `invalid_change_name` for a name that is not kebab-case, `change_exists` when the directory is already there.

## loopspec status

Report every node's derived status and name the single next command to run. This is the command an agent calls on every turn of the loop.

```bash
loopspec status <change-name> [--home <dir>] [--json]
```

| Option | Type | Default | Description |
| --- | --- | --- | --- |
| `CHANGE_NAME` | string | required | Positional argument: which change to inspect. |
| `--home` | path | `./loopspec` | Workflow home the change lives in. |
| `--json` | flag | off | Emit machine-readable JSON. |

Without `--json`, the command prints a fixed-layout plain-text report rather than the field-by-field `key: value` dump it used to. That default output is written for the LLM driving the loop, so a skill no longer has to add `--json` and parse JSON just to learn the next step. `--json` remains the source for callers that need exact fields. **Breaking change:** anything that grepped the old non-JSON output must pass `--json` now.

<!-- loopspec:example=status-report -->
```text
=== OVERVIEW ===
Where this change lives and whether it is finished. Paths here are absolute;
paths in every other section are relative to the artifact root.

change:        add-payment
schema:        secure-spec-driven
change root:   /Users/<you>/proj/loopspec/changes/add-payment
state.md:      present
complete:      no

=== NODES ===
Every node of the workflow, in dependency order. Columns: node id, status,
output path, then notes in parentheses. Statuses: done (output exists),
ready (dependencies met, output not written yet), blocked (waiting on the
nodes named in its notes), failed / exhausted (a gate rejected the work).
Do not pick a node yourself -- act on the one named in NEXT STEPS. A path
like dir/{a,b}.md means the node is a gate that writes exactly one of the
two; get the real paths from `loopspec instructions`. A node whose output
is a glob lists every file it currently matches, one per line, indented
under its first line; a path still containing * means that glob has no
matches yet. Notes describe the node, so they stay on its first line.

proposal  done     proposal.md
design    done     design.md
specs     done     specs/loopspec-cli/spec.md
                   specs/lpsx-skills/spec.md
                   specs/status-report/spec.md
tasks     done     tasks.md
security  done     security/pass.md
approval  ready    approval/{approved,changes-requested}.md
apply     blocked  apply/{report,blocked}.md                 (needs: approval)

=== NEXT STEPS ===
What to do next. Run these in order; the first one is enough to make
progress. Run them as written rather than composing your own.

1. Run `loopspec instructions approval --change add-payment --json`, then write the artifact per the returned template(s) and update state.md.
```

The report always has these sections, in this order:

| Section | Always present | What it renders |
| --- | --- | --- |
| `=== OVERVIEW ===` | yes | `changeName`, `schemaName`, `changeRoot`, `artifactRoot` (only when it differs from `changeRoot`), `stateExists`, `isComplete` |
| `=== NODES ===` | yes | One first line per `nodes[]` entry, plus one continuation line per extra glob match |
| `=== GATE FAILURES ===` | only when a gate is `failed` or `exhausted` | `nodes[].gate` |
| `=== PENDING ROLLBACK ===` | only when `pendingRollback` is non-null | `pendingRollback` |
| `=== NEXT STEPS ===` | yes | `nextSteps`, numbered; a placeholder line when it is empty |

Each section opens with a built-in paragraph explaining what it is and how to read it, so the report does not assume the reader already knows loopspec's node, gate and rollback concepts.

Reading the node list:

- Paths are relative to the artifact root, whose absolute form `=== OVERVIEW ===` gives once.
- A glob node lists **every** file it currently matches, the first on the node's own line and the rest on indented continuation lines. A path that still contains `*` means the glob matches nothing yet.
- A gate shows `dir/{pass,fail}.ext` until it has written a verdict, then the real path of the file it wrote. The brace form is a display form, not a path you can write to -- `loopspec instructions` returns the real ones.
- The note in parentheses is the node's, not a file's, and is exactly one of: missing dependencies, task progress, a pointer to `=== GATE FAILURES ===`, or "no matches yet".
- A match that resolved outside the artifact root -- a symlink pointing out of the change directory -- prints `<outside artifact root>` instead of where it pointed. Use `--json` for the resolved path.
- The list is **not** a parseable format: an output path may contain spaces, which makes column boundaries unreliable. Use `--json` when you need exact fields.

Control characters in any interpolated value are rewritten as `\xNN`, so a path, a verdict summary or a change name cannot open a new line and forge a `=== SECTION ===` header.

| Field | Type | Description |
| --- | --- | --- |
| `changeName` | string | The change's name. |
| `schemaName` | string | Schema in effect for this change. |
| `artifactsDir` | string | Value of `artifacts_dir` from `config.yaml`. |
| `schemaPath` | string or null | Artifact subdirectory declared by the schema reference, if any. |
| `changeRoot` | string | Absolute path of the change directory. |
| `artifactRoot` | string | Absolute path artifacts are resolved against. |
| `statePath` | string | Absolute path of `state.md`. |
| `stateExists` | boolean | Whether `state.md` is present. |
| `isComplete` | boolean | True only when every node is `done`. |
| `nodes` | array of object | One entry per node, in build order. |
| `nodes[].id` | string | Node id. |
| `nodes[].status` | string | `blocked`, `ready`, `done`, `failed` or `exhausted`. |
| `nodes[].outputPath` | string or object | Declared output. A string for plain nodes; `{pass, fail}` for gates. |
| `nodes[].resolvedOutputPath` | string, array, object or null | Absolute, and never a pattern: a concrete `generates` resolves to its path whether or not the file exists yet; a glob resolves to the array of files it currently matches, or `null` when it matches nothing. `{pass, fail}` for gates. |
| `nodes[].existingOutputPaths` | array of string | Which of those outputs currently exist on disk, absolute and sorted. Globs are expanded to the files they match. |
| `nodes[].missingDeps` | array of string | Present only when `blocked`: the required nodes that are not `done`. |
| `nodes[].taskProgress` | object | Present only for nodes declaring `tracks`. Counts only; the per-task list is in `instructions`. |
| `nodes[].taskProgress.path` | string | The tracked file, relative to the artifact root. |
| `nodes[].taskProgress.resolvedPath` | string | Absolute path of the tracked file. |
| `nodes[].taskProgress.total` | integer | Number of checkboxes found. |
| `nodes[].taskProgress.complete` | integer | Number ticked. |
| `nodes[].taskProgress.remaining` | integer | Number still unticked. |
| `nodes[].gate` | object | Present only when the node is `failed` or `exhausted`. |
| `nodes[].gate.verdict` | string | `FAIL`. |
| `nodes[].gate.summary` | string or null | First heading of the FAIL file, used as a one-line summary. |
| `nodes[].gate.blockingIssues` | array of string | Bullet items extracted from the FAIL file. |
| `nodes[].gate.rollbacksUsed` | integer | How many rollbacks this gate has already consumed. |
| `nodes[].gate.maxRetries` | integer | The gate's `on_fail.max_retries`. |
| `nodes[].gate.resetDeclared` | array of string | The gate's declared `on_fail.reset` list. |
| `nodes[].gate.resetClosure` | array of string | The full set of nodes a rollback would reset. |
| `pendingRollback` | object or null | Present when a gate is `failed`: the rollback that should run next. |
| `pendingRollback.gate` | string | The failed gate's node id. |
| `pendingRollback.closure` | array of string | Nodes the rollback will reset. |
| `pendingRollback.command` | string | The exact command to run. |
| `nextSteps` | array of string | The single next action, phrased as a runnable command. |

A freshly created change:

```json
{
  "changeName": "add-payment",
  "schemaName": "secure-spec-driven",
  "artifactsDir": "changes",
  "schemaPath": null,
  "changeRoot": "/path/to/project/loopspec/changes/add-payment",
  "artifactRoot": "/path/to/project/loopspec/changes/add-payment",
  "statePath": "/path/to/project/loopspec/changes/add-payment/state.md",
  "stateExists": true,
  "isComplete": false,
  "nodes": [
    {
      "id": "proposal",
      "status": "ready",
      "outputPath": "proposal.md",
      "resolvedOutputPath": "/path/to/project/loopspec/changes/add-payment/proposal.md",
      "existingOutputPaths": []
    },
    {
      "id": "specs",
      "status": "blocked",
      "outputPath": "specs/**/*.md",
      "resolvedOutputPath": null,
      "existingOutputPaths": [],
      "missingDeps": [
        "proposal"
      ]
    },
    {
      "id": "design",
      "status": "blocked",
      "outputPath": "design.md",
      "resolvedOutputPath": "/path/to/project/loopspec/changes/add-payment/design.md",
      "existingOutputPaths": [],
      "missingDeps": [
        "proposal"
      ]
    }
  ],
  "pendingRollback": null,
  "nextSteps": [
    "Run `loopspec instructions proposal --change add-payment --json`, then write the artifact per the returned template(s) and update state.md."
  ]
}
```

A change whose security gate has failed:

```json
{
  "nodes": [
    {
      "id": "security",
      "status": "failed",
      "outputPath": {
        "pass": "security/pass.md",
        "fail": "security/fail.md"
      },
      "resolvedOutputPath": {
        "pass": "/path/to/project/loopspec/changes/add-payment/security/pass.md",
        "fail": "/path/to/project/loopspec/changes/add-payment/security/fail.md"
      },
      "existingOutputPaths": [
        "/path/to/project/loopspec/changes/add-payment/security/fail.md"
      ],
      "gate": {
        "verdict": "FAIL",
        "summary": "Security Review: FAIL",
        "blockingIssues": [
          "Card numbers are logged in plaintext by the checkout handler.",
          "The refund endpoint has no authorization check."
        ],
        "rollbacksUsed": 0,
        "maxRetries": 3,
        "resetDeclared": [
          "design"
        ],
        "resetClosure": [
          "design",
          "tasks",
          "security",
          "approval",
          "apply"
        ]
      }
    }
  ],
  "pendingRollback": {
    "gate": "security",
    "closure": [
      "design",
      "tasks",
      "security",
      "approval",
      "apply"
    ],
    "command": "loopspec rollback add-payment --json"
  },
  "nextSteps": [
    "Gate \"security\" verdict is FAIL: Security Review: FAIL",
    "Run `loopspec rollback add-payment --json` to roll back, then regenerate the reset nodes."
  ]
}
```

## loopspec instructions

Return everything needed to produce one node's output: the instruction text, the template, where to write, which dependencies exist, and what previous attempts failed on.

```bash
loopspec instructions <node-id> --change <change-name> [--home <dir>] [--json]
```

| Option | Type | Default | Description |
| --- | --- | --- | --- |
| `NODE_ID` | string | required | Positional argument: which node to get instructions for. |
| `--change` | string | required | Which change the node belongs to. |
| `--home` | path | `./loopspec` | Workflow home the change lives in. |
| `--json` | flag | off | Emit machine-readable JSON. |

| Field | Type | Description |
| --- | --- | --- |
| `changeName` | string | The change's name. |
| `schemaName` | string | Schema in effect. |
| `changeDir` | string | Absolute path of the change directory. |
| `artifactRoot` | string | Absolute path artifacts are resolved against. |
| `nodeId` | string | The node id. |
| `description` | string | The node's one-line description from the schema. |
| `instruction` | string | The full instruction text: either the schema's inline string or the contents of the referenced instruction file. |
| `context` | string or null | Project-wide context from `config.yaml`. |
| `rules` | array of string | Extra rules configured for this node in `config.yaml`. |
| `dependencies` | array of object | One entry per node in `requires`. |
| `dependencies[].id` | string | Dependency node id. |
| `dependencies[].done` | boolean | Whether that dependency is complete. |
| `dependencies[].path` | string or null | Its artifact path — the PASS path for a gate. |
| `dependencies[].resolvedPath` | string, array or null | Absolute, and never a pattern: a concrete `generates` resolves to its path whether or not the file exists yet; a glob resolves to the array of files it currently matches, or `null` when it matches nothing. |
| `dependencies[].description` | string | The dependency's description. |
| `contextFiles` | object | Node id to the list of that node's currently existing output files, so a node can read the whole change without guessing filenames. Nodes with nothing on disk are omitted. |
| `unlocks` | array of string | Node ids that become unblocked once this node is done. |
| `statePath` | string | Absolute path of `state.md`. |
| `state` | string or null | Current contents of `state.md`; `null` when the file is missing. |
| `warnings` | array of string | Non-fatal problems, for example `state_missing`, a `rules` key naming an unknown node, or a missing tracked file. |
| `priorAttempts` | array of object | Past rollbacks that reset this node, oldest first. Empty on a first attempt. |
| `priorAttempts[].round` | integer | Which attempts round the failure belongs to. |
| `priorAttempts[].gate` | string | The gate that failed. |
| `priorAttempts[].verdict` | string | `FAIL`. |
| `priorAttempts[].summary` | string or null | One-line summary of that failure. |
| `priorAttempts[].blockingIssues` | array of string | The issues the next attempt must resolve. |
| `priorAttempts[].archivedPath` | string | Where this node's previous output was moved to. |
| `outputPath` | string or object | Where to write. A string for plain nodes; `{pass, fail}` for gates. |
| `resolvedOutputPath` | string, array, object or null | Absolute, and never a pattern: a concrete `generates` resolves to its path whether or not the file exists yet; a glob resolves to the array of files it currently matches, or `null` when it matches nothing. `{pass, fail}` for gates. |
| `template` | string | Present for plain nodes: the template file's contents. |
| `templates` | object | Present for gates: `{pass, fail}` template contents. |
| `taskProgress` | object | Present for nodes declaring `tracks`: the `status` counts plus a `tasks` array of `{id, description, done}`. |

```json
{
  "priorAttempts": [
    {
      "round": 1,
      "gate": "security",
      "verdict": "FAIL",
      "summary": "Security Review: FAIL",
      "blockingIssues": [
        "Card numbers are logged in plaintext by the checkout handler.",
        "The refund endpoint has no authorization check."
      ],
      "archivedPath": "/path/to/project/loopspec/changes/add-payment/.attempts/round-001/design.md"
    }
  ],
  "dependencies": [
    {
      "id": "proposal",
      "done": true,
      "path": "proposal.md",
      "resolvedPath": "/path/to/project/loopspec/changes/add-payment/proposal.md",
      "description": "Initial proposal document outlining the change"
    }
  ],
  "warnings": [],
  "unlocks": [
    "tasks"
  ]
}
```

Fails with `node_not_found` for an unknown node id, `change_not_found` for an unknown change.

## loopspec rollback

Roll back the change's currently failed gate: move every artifact in the reset closure into a fresh `.attempts/round-NNN/` directory, together with a `_meta.yaml` recording the verdict that caused it.

```bash
loopspec rollback <change-name> [--home <dir>] [--json]
```

| Option | Type | Default | Description |
| --- | --- | --- | --- |
| `CHANGE_NAME` | string | required | Positional argument: which change to roll back. |
| `--home` | path | `./loopspec` | Workflow home the change lives in. |
| `--json` | flag | off | Emit machine-readable JSON. |

Files are **moved, never deleted**. `state.md` and `.workflow.yaml` are never archived, so the change's memory survives every round. Rollback does not revert source code — only artifacts inside the change directory.

| Field | Type | Description |
| --- | --- | --- |
| `changeName` | string | The change's name. |
| `gate` | string | The gate that was rolled back. |
| `round` | integer | The round number this rollback created. |
| `closure` | array of string | Nodes that were reset, in topological order. |
| `archivedFiles` | array of string | Artifact paths that were moved, relative to the artifact root. |
| `archiveDir` | string | Absolute path of the `.attempts/round-NNN/` directory. |
| `rollbacksUsed` | integer | How many rollbacks this gate has now consumed. |
| `maxRetries` | integer | The gate's `on_fail.max_retries`. |
| `nextSteps` | array of string | Suggested follow-up commands. |

```json
{
  "changeName": "add-payment",
  "gate": "security",
  "round": 1,
  "closure": [
    "design",
    "tasks",
    "security",
    "approval",
    "apply"
  ],
  "archivedFiles": [
    "design.md",
    "tasks.md",
    "security/fail.md"
  ],
  "archiveDir": "/path/to/project/loopspec/changes/add-payment/.attempts/round-001",
  "rollbacksUsed": 1,
  "maxRetries": 3,
  "nextSteps": [
    "Run `loopspec status add-payment --json` to see the next node."
  ]
}
```

Fails with `no_failed_gate` when nothing is in a failed state, or `retries_exhausted` when the only actionable gate has already used up `max_retries`:

```json
{
  "error": "no_failed_gate",
  "message": "No gate is currently in a failed state; there is nothing to roll back.",
  "fix": "Run `loopspec status` to see the current state."
}
```

## loopspec history

List every attempts round recorded for a change.

```bash
loopspec history <change-name> [--home <dir>] [--json]
```

| Option | Type | Default | Description |
| --- | --- | --- | --- |
| `CHANGE_NAME` | string | required | Positional argument: which change to read history for. |
| `--home` | path | `./loopspec` | Workflow home the change lives in. |
| `--json` | flag | off | Emit machine-readable JSON. |

| Field | Type | Description |
| --- | --- | --- |
| `changeName` | string | The change's name. |
| `rounds` | array of object | One entry per `.attempts/round-NNN/` directory, oldest first. |
| `rounds[].round` | integer | Round number. |
| `rounds[].gate` | string | The gate that failed. |
| `rounds[].verdict` | string | `FAIL`. |
| `rounds[].summary` | string or null | One-line summary of the failure. |
| `rounds[].resetClosure` | array of string | Nodes that were reset. |
| `rounds[].archivedFiles` | array of string | Artifact paths that were moved. |
| `rounds[].archiveDir` | string | Absolute path of the round directory. |
| `rounds[].archivedAt` | string | ISO-8601 timestamp of the rollback. |

```json
{
  "changeName": "add-payment",
  "rounds": [
    {
      "round": 1,
      "gate": "security",
      "verdict": "FAIL",
      "summary": "Security Review: FAIL",
      "resetClosure": [
        "design",
        "tasks",
        "security",
        "approval",
        "apply"
      ],
      "archivedFiles": [
        "design.md",
        "tasks.md",
        "security/fail.md"
      ],
      "archiveDir": "/path/to/project/loopspec/changes/add-payment/.attempts/round-001",
      "archivedAt": "2026-07-29T17:00:11.952957+08:00"
    }
  ]
}
```

## loopspec artifacts

List every artifact path a change name owns — across every schema that worked it and every location it lives in, the archive included.

```bash
loopspec artifacts <change-name> [--schemas <names>] [--home <dir>] [--json]
```

| Option | Type | Default | Description |
| --- | --- | --- | --- |
| `CHANGE_NAME` | string | required | Positional argument: which change to list artifacts for. |
| `--schemas` | string | every known schema | Comma-separated schema names to report artifacts for (e.g. `secure-spec-driven,docs-only`). |
| `--home` | path | `./loopspec` | Workflow home to search. |
| `--json` | flag | off | Emit machine-readable JSON. |

This command answers a question no other command can. `status` and `instructions` both resolve **one** schema — the one in `.workflow.yaml` — under a change directory that still exists. That breaks down in two situations:

- **Schema relay.** Several schemas work one change in turn. `.workflow.yaml` holds a single `schema` field, so migrating a change to another workflow overwrites the previous schema's name, and each schema's artifacts may sit under a different `schemas[*].path` root that the current schema's patterns cannot match.
- **Archiving.** `loopspec archive` *moves* the whole directory to `<home>/archive/YYYY-MM/<change>/`. Once a stretch of work is archived, `status` fails with `change_not_found` and the artifacts of that stretch are unreachable through it — even though "finish, archive, carry on under the same name" is the most common shape a relay takes.

`artifacts` therefore spans three axes at once:

| Axis | What is covered |
| --- | --- |
| Location | The active directory plus **every** archive month. `ArchiveConflictError` only prevents same-month collisions, so one name can have a copy under several months; each match comes back as its own location. |
| Schema | Every schema in scope is *probed*: its `schemas[*].path` gives an artifact root, and its nodes' output patterns are matched against files that actually exist. Nothing is assumed from `.workflow.yaml`. |
| Round | Each `.attempts/round-NNN/` directory in each location, reported separately from the current artifacts. |

Three consequences worth knowing:

- **Attribution is a projection of the schemas as they are defined right now, not a record of history.** Editing a schema's `generates` changes how an old change's files are grouped. Files are never lost to this — they move into `unclassifiedFiles` instead.
- **`unclassifiedFiles` is the completeness backstop.** Any file that exists but matches no probed pattern is reported there: leftovers from a deleted schema, renamed artifacts, attachments someone dropped in by hand. Hidden files are not filtered out either, so `.DS_Store` will show up — visible noise is preferable to a listing that silently omits things.
- **Paths that resolve outside the workflow home are skipped.** Resolution follows symlinks, so a link inside a change directory pointing elsewhere on the filesystem is dropped from every list and named in `warnings` by its relative name only. The rest of that location reports normally.

`state.md` and `.workflow.yaml` are not artifacts (the same rule the rest of the CLI uses), but each location reports `statePath` and `stateExists` regardless: a relay needs the previous stretch's decisions as much as its files.

The command is read-only. It never creates, moves or deletes anything, including in the archive.

Locations come back oldest-first — archive months ascending, then the active directory. That order is part of the contract: a relay reads the earlier stretches before the current one, so the list can be walked as-is.

| Field | Type | Description |
| --- | --- | --- |
| `changeName` | string | The change's name. |
| `artifactsDir` | string | The value of `artifacts_dir` from `config.yaml`. |
| `requestedSchemas` | array of string or null | The names passed to `--schemas`; `null` when the option was omitted, which is not the same as an empty list. |
| `schemasSeen` | array of string | The schemas actually probed, sorted. |
| `locations` | array of object | One entry per place this change's artifacts live, oldest first. |
| `locations[].kind` | string | `active` or `archived`. |
| `locations[].archiveMonth` | string or null | The archive month directory's name; `null` for the active location. |
| `locations[].changeRoot` | string | Absolute path of this location's change directory. |
| `locations[].declaredSchema` | string or null | The schema this location's `.workflow.yaml` names; `null` when that file is missing or unreadable. |
| `locations[].created` | string or null | The `created` date from the same file. |
| `locations[].statePath` | string | Absolute path of this location's `state.md`. |
| `locations[].stateExists` | boolean | Whether that file is present. |
| `locations[].schemas` | array of object | One entry per probed schema, sorted by name. |
| `locations[].schemas[].name` | string | Schema name. |
| `locations[].schemas[].declared` | boolean | Whether this location's `.workflow.yaml` names this schema. False is normal — that is what a relay looks like. |
| `locations[].schemas[].schemaPath` | string or null | The `path` from this schema's config entry, if any. |
| `locations[].schemas[].artifactRoot` | string | Absolute path the probe resolved against. |
| `locations[].schemas[].nodes` | array of object | Nodes with at least one existing output, in build order. Nodes with nothing on disk are omitted. |
| `locations[].schemas[].nodes[].id` | string | Node id. |
| `locations[].schemas[].nodes[].isGate` | boolean | Whether the node declares a `gate` block. |
| `locations[].schemas[].nodes[].outputPatterns` | array of string | The declared patterns this node was probed with — for a gate, its PASS and FAIL outputs. |
| `locations[].schemas[].nodes[].files` | array of string | Existing files matched for this node. |
| `locations[].schemas[].files` | array of string | Every file claimed by this schema in this location, de-duplicated. |
| `locations[].attempts` | array of object | One entry per rollback round directory. |
| `locations[].attempts[].round` | integer or null | Round number from the directory name; `null` when the name is not `round-<digits>`. Such a directory is still reported, so the files inside it are not lost. |
| `locations[].attempts[].gate` | string or null | The gate recorded in that round's `_meta.yaml`; `null` when it is missing or unreadable. |
| `locations[].attempts[].verdict` | string or null | The verdict from the same file. |
| `locations[].attempts[].archiveDir` | string | Absolute path of the round directory. |
| `locations[].attempts[].files` | array of string | Files archived in that round, excluding its `_meta.yaml`. |
| `locations[].unclassifiedFiles` | array of string | Files in this location that no probed schema claimed. |
| `locations[].files` | array of string | Every artifact path in this location, de-duplicated and sorted. |
| `files` | array of string | Every artifact path across all locations, de-duplicated and sorted. |
| `warnings` | array of string | Non-fatal problems: unreadable metadata, a schema that could not be loaded, a file claimed by more than one schema, a path that resolved outside the workflow home. |
| `nextSteps` | array of string | The suggested follow-up command. |

A change that has been archived once and restarted under the same name:

```json
{
  "changeName": "add-payment",
  "artifactsDir": "changes",
  "requestedSchemas": null,
  "schemasSeen": [
    "docs-only",
    "secure-spec-driven"
  ],
  "locations": [
    {
      "kind": "archived",
      "archiveMonth": "2026-06",
      "changeRoot": "/path/to/project/loopspec/archive/2026-06/add-payment",
      "declaredSchema": "secure-spec-driven",
      "created": "2026-06-11",
      "statePath": "/path/to/project/loopspec/archive/2026-06/add-payment/state.md",
      "stateExists": true,
      "schemas": [
        {
          "name": "secure-spec-driven",
          "declared": true,
          "schemaPath": null,
          "artifactRoot": "/path/to/project/loopspec/archive/2026-06/add-payment",
          "nodes": [
            {
              "id": "proposal",
              "isGate": false,
              "outputPatterns": [
                "proposal.md"
              ],
              "files": [
                "/path/to/project/loopspec/archive/2026-06/add-payment/proposal.md"
              ]
            }
          ],
          "files": [
            "/path/to/project/loopspec/archive/2026-06/add-payment/proposal.md"
          ]
        }
      ],
      "attempts": [
        {
          "round": 1,
          "gate": "security",
          "verdict": "FAIL",
          "archiveDir": "/path/to/project/loopspec/archive/2026-06/add-payment/.attempts/round-001",
          "files": [
            "/path/to/project/loopspec/archive/2026-06/add-payment/.attempts/round-001/design.md"
          ]
        }
      ],
      "unclassifiedFiles": [],
      "files": [
        "/path/to/project/loopspec/archive/2026-06/add-payment/.attempts/round-001/design.md",
        "/path/to/project/loopspec/archive/2026-06/add-payment/proposal.md"
      ]
    }
  ],
  "files": [
    "/path/to/project/loopspec/archive/2026-06/add-payment/.attempts/round-001/design.md",
    "/path/to/project/loopspec/archive/2026-06/add-payment/proposal.md"
  ],
  "warnings": [],
  "nextSteps": [
    "Every copy of this change is archived; read the listed paths directly, or run `loopspec new add-payment --schema <name>` to start a new stretch of work under this name."
  ]
}
```

Without `--json`, the command prints one section per location with counts rather than paths — schema names and how many files each claimed, unclaimed count, rollback rounds, whether `state.md` is present — then a total. The full path detail stays available through `--json`.

Failures: a change name that no location matches reports `change_not_found`; a name that is not a safe relative path reports `invalid_change_name`; a `--schemas` value that strips to nothing, or contains a name that is not kebab-case, reports `config_invalid`. Naming a schema that cannot be loaded reports `schema_not_found` or `schema_invalid` rather than returning an empty result — otherwise "this schema produced nothing" and "you misspelled the name" would be indistinguishable. Schemas that were merely *inferred* (from `config.yaml` candidates or a location's own `.workflow.yaml`) degrade to a warning instead, so dropping a candidate from the config never makes old artifacts vanish.

## loopspec archive

Move one finished change into `<home>/archive/YYYY-MM/`, where `YYYY-MM` is the current year and month in UTC.

```bash
loopspec archive <change-name> [--dry-run] [--exhausted] [--include-pending-failures] [--home <dir>] [--json]
```

| Option | Type | Default | Description |
| --- | --- | --- | --- |
| `CHANGE_NAME` | string | required | Positional argument: which change to archive. |
| `--dry-run` | flag | off | Report what would move, change nothing on disk. |
| `--exhausted` | flag | off | Also allow archiving a change stuck on an `exhausted` gate, provided no gate is merely `failed`. |
| `--include-pending-failures` | flag | off | Also allow archiving a change with a `failed` gate that could still be rolled back. |
| `--home` | path | `./loopspec` | Workflow home the change lives in. |
| `--json` | flag | off | Emit machine-readable JSON. |

Archiving **moves** the directory; nothing is deleted. It runs immediately by default — there is no confirmation flag — but refuses any change that does not qualify:

- Complete changes always qualify.
- An `exhausted` change qualifies only with `--exhausted`, and only when nothing is `failed`.
- A `failed` change qualifies only with `--include-pending-failures`.
- Anything else exits 1 with `archive_unsafe`.

| Field | Type | Description |
| --- | --- | --- |
| `dryRun` | boolean | Whether this was a preview. |
| `changeName` | string | The change's name. |
| `schemaName` | string | Schema the change used. |
| `reason` | string | Why it qualified: `complete`, `exhausted` or `pending-failure`. |
| `source` | string | Absolute path the change is moving from. |
| `destination` | string | Absolute path it is moving to. |
| `moved` | boolean | Present only on a real run: always `true`. |
| `nextSteps` | array of string | Suggested follow-up. |

```json
{
  "dryRun": false,
  "changeName": "add-payment",
  "schemaName": "secure-spec-driven",
  "reason": "complete",
  "source": "/path/to/project/loopspec/changes/add-payment",
  "destination": "/path/to/project/loopspec/archive/2026-07/add-payment",
  "moved": true,
  "nextSteps": [
    "Archiving complete."
  ]
}
```

An unfinished change is refused:

```json
{
  "error": "archive_unsafe",
  "message": "This change is not complete and does not qualify for archiving under the current flags.",
  "fix": "Finish the change, or pass --exhausted / --include-pending-failures if that applies."
}
```

`archive_conflict` is raised instead when the destination already exists, so an earlier archive of the same name is never overwritten.

## loopspec bulk-archive

Archive every qualifying change in one pass.

```bash
loopspec bulk-archive [--complete] [--exhausted] [--older-than <days>] [--dry-run] [--home <dir>] [--json]
```

| Option | Type | Default | Description |
| --- | --- | --- | --- |
| `--complete` | flag | on | Accepted for symmetry with `--exhausted`. Complete changes are always candidates, so passing it changes nothing. |
| `--exhausted` | flag | off | Also archive changes stuck on an `exhausted` gate. |
| `--older-than` | integer | unset | Only consider changes whose directory was last modified at least this many days ago. |
| `--dry-run` | flag | off | Report the candidate list, change nothing on disk. |
| `--home` | path | `./loopspec` | Workflow home to scan. |
| `--json` | flag | off | Emit machine-readable JSON. |

Changes that do not qualify are skipped silently rather than failing the run. Unlike single-change `archive`, bulk archiving never accepts pending failures — a `failed` gate always disqualifies.

| Field | Type | Description |
| --- | --- | --- |
| `dryRun` | boolean | Whether this was a preview. |
| `archiveRoot` | string | Destination directory for this month. |
| `candidates` | array of object | Changes that qualify, each shaped like an `archive --dry-run` result. |
| `moved` | array of object | Present only on a real run: the changes actually moved. |
| `nextSteps` | array of string | Suggested follow-up. |

```json
{
  "dryRun": true,
  "archiveRoot": "/path/to/project/loopspec/archive/2026-07",
  "candidates": [
    {
      "dryRun": true,
      "changeName": "add-payment",
      "schemaName": "secure-spec-driven",
      "reason": "complete",
      "source": "/path/to/project/loopspec/changes/add-payment",
      "destination": "/path/to/project/loopspec/archive/2026-07/add-payment",
      "nextSteps": [
        "Re-run without --dry-run to move this change into the archive."
      ]
    }
  ],
  "nextSteps": [
    "Re-run without --dry-run to move these changes into the archive."
  ]
}
```

## Error codes

Every failure exits 1 and reports one of these codes in the `error` field.

| Code | Raised when | Fix direction |
| --- | --- | --- |
| `schema_not_found` | No `schema.yaml` exists at the resolved schema directory. | Create the file, or point at the right schema name. |
| `schema_selection_required` | `config.yaml` lists several candidate schemas and `loopspec new` got no `--schema`. | Pick one of `schemas[*].name` and pass `--schema`. The error payload carries the candidates. |
| `schema_invalid` | A schema fails structural validation (unknown field, bad type) or any semantic check (duplicate ids, unknown `requires`, cycles, gate output problems, bad `on_fail.reset`, bad `tracks`, reserved output path). | Fix the reported node or field; see [Schema reference](schema-reference.md). |
| `config_invalid` | `config.yaml` is missing, fails validation, or contains an unsafe relative path. | Correct the reported field in `config.yaml`. |
| `template_not_found` | A node's `template`, or a gate's pass/fail template, does not exist under the schema's `templates/`. | Add the template file, or fix the name in `schema.yaml`. |
| `instruction_not_found` | A node's `instruction.file` does not exist under the schema's `instructions/`. | Add the instruction file, or fix the name in `schema.yaml`. |
| `change_not_found` | The named change directory does not exist in this workflow home. | Check the name, or check `--home`. |
| `change_exists` | `loopspec new` was given a name whose directory already exists. | Pick a different name, or continue the existing change. |
| `invalid_change_name` | The change name is not kebab-case. | Rename to match `^[a-z][a-z0-9]*(-[a-z0-9]+)*$`. |
| `node_not_found` | `loopspec instructions` was given a node id the schema does not define. | Run `loopspec schemas show` to list the real node ids. |
| `gate_output_conflict` | Both the PASS and FAIL files of one gate exist, so the verdict is ambiguous. | Delete whichever file does not reflect the real verdict. |
| `no_failed_gate` | `loopspec rollback` ran while no gate is in the `failed` state. | Run `loopspec status` to see what the change actually needs. |
| `retries_exhausted` | `loopspec rollback` ran while the only actionable gate is `exhausted`. | Review `loopspec history` and escalate to a human. |
| `archive_conflict` | The archive destination path already exists. | Rename or remove the existing archived copy first. |
| `archive_unsafe` | The change does not qualify for archiving under the flags given. | Finish the change, or pass `--exhausted` / `--include-pending-failures` if that applies. |
