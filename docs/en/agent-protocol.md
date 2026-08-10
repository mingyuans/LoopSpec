# Agent protocol

> Scope: the exact loop an LLM agent runs to drive a change to completion, which response field to read at each step, and the four behaviours that are easy to get wrong.
> Audience: LLM agents driving LoopSpec, and humans writing the prompts that drive them.
> Language: **English** · [中文](../zh/agent-protocol.md)

Always pass `--json` — with one exception: `loopspec status`, whose default output is already the report an agent should read (add `--json` there only when you need exact field values). Always read `nextSteps`. Never infer the next step from filenames or from memory of an earlier turn — the filesystem is the source of truth and it may have changed.

## The main loop

```text
loopspec status <change>
        |
        v
read nextSteps  ---> names exactly one command to run
        |
        v
loopspec instructions <node> --change <change> --json
        |
        v
do what `instruction` says, write to `resolvedOutputPath`, update state.md
        |
        +--------> back to status
```

| Step | Command | Field to read | What to do with it |
| --- | --- | --- | --- |
| 1 | `loopspec status <change>` | `nextSteps` | Names exactly one command. Run it. Do not pick a node yourself. |
| 2 | *(same response)* | `isComplete` | `true` means every node is done; stop looping and archive. |
| 3 | *(same response)* | `pendingRollback` | Non-null means a gate failed. Take the [rollback branch](#the-rollback-branch) instead of continuing. |
| 4 | `loopspec instructions <node> --change <change> --json` | `instruction` | The task. It is not always "write a file" — see [Nodes that are not documents](#nodes-that-are-not-documents). |
| 5 | *(same response)* | `template` or `templates` | The skeleton to follow. Gates get both `templates.pass` and `templates.fail`. |
| 6 | *(same response)* | `resolvedOutputPath` | Absolute path to write. For a gate this is an object: write to exactly one of `.pass` or `.fail`. |
| 7 | *(same response)* | `contextFiles` | Real paths of every artifact that already exists, keyed by node id. Read these rather than guessing filenames. |
| 8 | *(same response)* | `dependencies` | The upstream nodes, each with `resolvedPath` and whether it is `done`. |
| 9 | *(same response)* | `priorAttempts` | Non-empty means this node was reset by a failed gate. Read `blockingIssues` and resolve every one. |
| 10 | *(same response)* | `context` and `rules` | Project-wide context and node-specific rules from `config.yaml`. Honour both. |
| 11 | *(same response)* | `warnings` | Non-fatal problems worth acting on, such as `state_missing`. |
| 12 | *(same response)* | `state` and `statePath` | The change's memory. Read before writing, then append your decisions. |
| 13 | — | — | Go back to step 1. |

### Reading `status` without `--json`

The default output is a plain-text report whose sections carry the same information the JSON does:

| Section | JSON it corresponds to |
| --- | --- |
| `=== OVERVIEW ===` | `changeName`, `schemaName`, `changeRoot`, `artifactRoot`, `stateExists`, `isComplete` |
| `=== NODES ===` | `nodes[]` — one first line per node, plus an indented continuation line per extra glob match |
| `=== GATE FAILURES ===` | `nodes[].gate`, present only when a gate is `failed` or `exhausted` |
| `=== PENDING ROLLBACK ===` | `pendingRollback`, present only when it is non-null |
| `=== NEXT STEPS ===` | `nextSteps` |

Each section opens with a paragraph explaining how to read it, so the report is self-describing. Two things it does not give you: absolute paths for individual outputs (it prints them relative to the artifact root, whose absolute form is in `=== OVERVIEW ===`), and a parseable node list (output paths may contain spaces). When you need either, pass `--json`. Full layout and an example are in the [CLI reference](cli-reference.md#loopspec-status).

Repeat until `isComplete` is `true`, then archive:

```bash
loopspec archive <change> --json
```

## The rollback branch

When a gate's verdict is FAIL, `status` reports that node as `failed` and fills in `pendingRollback`. The loop changes shape:

| Step | Command | Field to read | What to do with it |
| --- | --- | --- | --- |
| 1 | `loopspec status <change>` | `pendingRollback.command` | The exact rollback command. Run it verbatim. |
| 2 | *(same response)* | `pendingRollback.closure` | Which nodes are about to be reset, so you know how much work is coming. |
| 3 | `loopspec rollback <change> --json` | `archivedFiles`, `archiveDir` | What was moved aside, and where to find it. Nothing was deleted. |
| 4 | *(same response)* | `rollbacksUsed`, `maxRetries` | How much budget is left before the gate becomes `exhausted`. |
| 5 | `loopspec status <change>` | `nextSteps` | Resume the main loop; the reset nodes are `ready` again. |
| 6 | `loopspec instructions <node> ...` | `priorAttempts[].blockingIssues` | The reason the previous attempt was rejected. Resolve each issue concretely — a rewording that leaves the same problem in place will fail the gate again. |

A gate reported as `exhausted` cannot be rolled back again; `loopspec rollback` refuses with `retries_exhausted`. Read `loopspec history <change> --json` for the full record of past rounds and escalate to a human.

## Nodes that are not documents

Three behaviours surprise agents that assume every node means "write one markdown file".

### Gates write one of two files

A gate node's `resolvedOutputPath` is an object, not a string. Write to `.pass` or `.fail` — never both. Both existing raises `gate_output_conflict` on the next command, and the change cannot proceed until one is deleted.

### A tracked node is not done when its report is written

A node declaring `tracks` stays `ready` until every checkbox in the tracked file is ticked, even after its PASS output exists. This is deliberate: it makes an implementation node wait for the actual work.

The practical consequences:

- Writing `apply/report.md` while tasks remain unticked leaves `apply` at `ready`, not `done`.
- `isComplete` stays `false`.
- `loopspec archive` refuses with `archive_unsafe`.

So tick each checkbox in the tracked file as you finish that task — `- [ ]` to `- [x]` — rather than batching the edits at the end. Checkbox state is how progress survives an interrupted session. `status` reports `taskProgress` counts per tracked node, and `instructions` adds the per-task list.

### A human approval gate is not yours to decide

If a schema has a node whose instruction asks for a human decision, the verdict belongs to the human. Summarise the plan, ask using your host tool's interactive question facility, and record whatever the human answers.

If you have no way to reach a human, or the human has not answered yet, write **neither** output file and stop, reporting that the change is waiting on approval. The node stays `ready`, which is the correct state for "waiting on a person". A fabricated PASS defeats the entire purpose of the gate.

## Working with state.md

`state.md` is the change's working memory. It lives in the change directory, is returned in full as the `state` field of every `loopspec instructions` response, and is the one file a rollback never touches. When `warnings` contains `state_missing`, recreate it with the six standard sections:

```markdown
# Change State

## Current Focus
## Frozen Decisions
## Decision Log
## Rejected Options
## Open Questions
## Artifact Notes
```

Rules that make it useful rather than decorative:

- **Append, do not rewrite.** Existing entries are the record of earlier rounds. Since `state.md` has no `.attempts/` history, an overwrite is unrecoverable.
- **Every entry must stand alone.** Replace every pronoun and deictic reference — "this", "that", "it", "the one above" — with what it refers to: a capability name, a file path, a task number, a node id. Later nodes read `state.md` with none of the current conversation's context, so an entry containing "that" looks like information but cannot be resolved.
- **Keep qualifiers intact.** "Fine, but X has to land first" must not be distilled into "fine".
- **Verbatim human words go in the verdict file**, not in `state.md`. `state.md` gets the distilled point plus the path to the verdict file, so anyone who needs the exact wording knows where to look.

## Reading a change you did not create

Three commands orient you without touching anything:

```bash
loopspec artifacts <change> --json
loopspec status <change>
loopspec history <change> --json
```

Start with `artifacts`. It is the only one that answers "what exists under this name at all", because it is the only one that is not scoped to a single schema in a single directory: it reports every location (the active directory **and** every archive month), every schema that left files behind, and every rollback round. Read its `locations` in order — oldest first — and you are reading the change chronologically.

Then `status` gives the current shape: what is done, what is next, whether a gate has failed. `history` gives the past *within the current location*: every attempts round, which gate failed, and where the archived artifacts went. Then `loopspec instructions <node>` for the `ready` node hands you `contextFiles` — the real paths of everything the current schema produced — plus `state` for the decisions behind them.

The division matters when a change has been worked by more than one schema in turn, which happens two ways: `.workflow.yaml` was migrated to another schema, or an earlier stretch was archived and a new one started under the same name. In both cases the earlier artifacts are invisible to `status` and `contextFiles` — the first because the previous schema's patterns no longer apply, the second because `status` fails with `change_not_found` once the directory has moved. So when you are continuing work someone (or some other schema) started:

| Step | Command | What to read | Why |
| --- | --- | --- | --- |
| 1 | `loopspec artifacts <change> --json` | `locations[].files` | Every file that exists under this name, wherever it lives. |
| 2 | `loopspec artifacts <change> --json` | `locations[].statePath` | Each location's `state.md`. The earlier stretch's decisions are here, not in the current one. |
| 3 | `loopspec artifacts <change> --json` | `warnings` | Unreadable metadata, files claimed by two schemas, paths skipped for resolving outside the workflow home. |
| 4 | `loopspec status <change>` | `nextSteps` | Back to the main loop for the active stretch. |

Two things not to misread in that response. Attribution under `locations[].schemas[]` reflects how the schemas are defined **right now** — it is a projection, not a record of which schema historically wrote what. And `locations[].unclassifiedFiles` is not a leftovers bin to ignore: a file lands there whenever no probed schema claims it, which includes artifacts of a schema that has since been deleted. Read those paths too.

## Checklist

- Pass `--json` to every command.
- Run the one command `nextSteps` names; do not choose a node yourself.
- Read `contextFiles` instead of guessing filenames.
- Resolve every `priorAttempts[].blockingIssues` entry before rewriting a reset node.
- Write to exactly one of a gate's two output paths.
- Tick tracked checkboxes as you go, not at the end.
- Never approve on a human's behalf.
- Append to `state.md`; never overwrite it.

## Next

- [CLI reference](cli-reference.md) — every field of every response.
- [secure-spec-driven](workflows/secure-spec-driven.md) — the built-in workflow's node-by-node expectations.
