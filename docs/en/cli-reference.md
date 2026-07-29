# CLI reference

> Scope: every `loopspec` command — purpose, syntax, options, `--json` response fields, worked examples — plus the error code table.
> Audience: humans looking up a flag, and LLM agents that need the exact response shape.
> Language: **English** · [中文](../zh/cli-reference.md)

Every command accepts `--json`. That is the primary protocol for driving LoopSpec from an agent;
without it you get a plain-text summary meant for a person. Both modes present the same facts, but
the human-readable mode is allowed to aggregate (counts instead of full path lists).

Two options recur on nearly every command:

| Option | Type | Default | Description |
| --- | --- | --- | --- |
| `--home` | path | `./loopspec` | The workflow home to operate on. See [workflow home](overview.md#glossary). |
| `--json` | flag | off | Emit machine-readable JSON on stdout instead of the human summary. |

All JSON paths in the examples below are shown rooted at `/path/to/project` — real output contains
absolute paths on your machine.

## Failure contract

Every command that fails exits with code **1** and, in `--json` mode, prints an object with exactly
three fields:

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
| `version` | string | Installed package version. Falls back to the source tree's `__version__` when the package metadata is unavailable. |

```json
{"version": "0.1.0"}
```

## loopspec init

Create a workflow home, copy the built-in schemas into it, and optionally scaffold skill and
slash-command files for AI coding tools.

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

`init` is idempotent: an existing `config.yaml` is left alone, and a schema directory that already
exists is not overwritten. Re-running it refreshes tool scaffolding rather than duplicating it.

### How `--tools` resolves

- Explicit value (`all`, `none`, or a list) is always honoured.
- Omitted, in an interactive terminal, without `--json`: a welcome screen and a searchable
  multi-select over all 31 registered tools. On a first-time setup the tools whose directories are
  already present start checked; once anything is configured, later runs pre-select what is
  *configured* instead. Confirming with nothing checked equals `none`, and Ctrl+C is treated as
  "configure nothing this run" rather than an error.
- Omitted, non-interactively (pipes, redirects, CI) or with `--json`: equivalent to `none`.

Skill files are written to `<project root>/<tool dir>/skills/loopspec-*/SKILL.md` for every selected
tool. Slash commands are written only for tools that have a command adapter; 28 of the 31 registered
tools do, and the three that do not (`forgecode`, `kimi`, `vibe`) are reported in
`skippedCommandGeneration`.

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

Without `--json`, `init` prints a sectioned summary: a `Created:` or `Refreshed:` tool list, an
aggregate count line, the config path and its schema, any skipped command generation, a
`Getting started:` command, and documentation links. Colour and the progress spinner drop out
automatically when stdout is not a terminal or `NO_COLOR` is set, and the Unicode glyphs fall back to
ASCII (`ok`, `x`, `!`, `-`, `|`) when the output encoding cannot represent them.

## loopspec schemas list

List every loadable schema in the workflow home.

```bash
loopspec schemas list [--home <dir>] [--json]
```

| Option | Type | Default | Description |
| --- | --- | --- | --- |
| `--home` | path | `./loopspec` | Workflow home to scan. |
| `--json` | flag | off | Emit machine-readable JSON. |

A directory under `<home>/schemas/` without a `schema.yaml`, or with one that fails to load, is
skipped silently rather than failing the whole listing.

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

Fails with `schema_not_found` when no `schema.yaml` exists at that path, or `schema_invalid` when it
exists but does not validate.

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

This is the command to use while authoring a schema. See
[Schema reference](schema-reference.md) for the full list of checks and the error code each one
raises.

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

The chosen schema is written to the change's `.workflow.yaml`, so later commands operate on the same
schema even if the project default changes. See
[Configuration](configuration.md) for the full resolution order.

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

When `config.yaml` lists several candidate schemas and `--schema` was not given, the command exits 1
with `schema_selection_required` and, unusually for an error, includes the candidate list so a caller
can present the choice:

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

Other failures: `invalid_change_name` for a name that is not kebab-case, `change_exists` when the
directory is already there.

## loopspec status

Report every node's derived status and name the single next command to run. This is the command an
agent calls on every turn of the loop.

```bash
loopspec status <change-name> [--home <dir>] [--json]
```

| Option | Type | Default | Description |
| --- | --- | --- | --- |
| `CHANGE_NAME` | string | required | Positional argument: which change to inspect. |
| `--home` | path | `./loopspec` | Workflow home the change lives in. |
| `--json` | flag | off | Emit machine-readable JSON. |

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
| `nodes[].resolvedOutputPath` | string or object | The same, resolved to absolute paths. |
| `nodes[].existingOutputPaths` | array of string | Which of those outputs currently exist on disk. |
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

Return everything needed to produce one node's output: the instruction text, the template, where to
write, which dependencies exist, and what previous attempts failed on.

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
| `dependencies[].resolvedPath` | string or null | The same, absolute. |
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
| `resolvedOutputPath` | string or object | The same, absolute. |
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

Roll back the change's currently failed gate: move every artifact in the reset closure into a fresh
`.attempts/round-NNN/` directory, together with a `_meta.yaml` recording the verdict that caused it.

```bash
loopspec rollback <change-name> [--home <dir>] [--json]
```

| Option | Type | Default | Description |
| --- | --- | --- | --- |
| `CHANGE_NAME` | string | required | Positional argument: which change to roll back. |
| `--home` | path | `./loopspec` | Workflow home the change lives in. |
| `--json` | flag | off | Emit machine-readable JSON. |

Files are **moved, never deleted**. `state.md` and `.workflow.yaml` are never archived, so the
change's memory survives every round. Rollback does not revert source code — only artifacts inside
the change directory.

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

Fails with `no_failed_gate` when nothing is in a failed state, or `retries_exhausted` when the only
actionable gate has already used up `max_retries`:

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

## loopspec archive

Move one finished change into `<home>/archive/YYYY-MM/`, where `YYYY-MM` is the current year and
month in UTC.

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

Archiving **moves** the directory; nothing is deleted. It runs immediately by default — there is no
confirmation flag — but refuses any change that does not qualify:

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

`archive_conflict` is raised instead when the destination already exists, so an earlier archive of
the same name is never overwritten.

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

Changes that do not qualify are skipped silently rather than failing the run. Unlike single-change
`archive`, bulk archiving never accepts pending failures — a `failed` gate always disqualifies.

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
