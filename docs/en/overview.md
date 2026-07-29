# Overview

> Scope: what LoopSpec is, the problem it solves, its core model, and the glossary every other page relies on.
> Audience: humans and LLM agents, first page to read.
> Language: **English** · [中文](../zh/overview.md)

## What LoopSpec is

LoopSpec is a command-line tool for running **gated artifact workflows**: you declare, in YAML, a graph of documents that a change has to produce (proposal, specs, design, tasks, ...) and the dependencies between them. An LLM generates those documents one at a time. Some nodes in the graph are **gates**: instead of another document they produce a PASS or FAIL verdict, and a FAIL rolls the change back to a declared upstream node so the work can be redone with full knowledge of why the previous attempt failed.

LoopSpec does not generate anything itself. It answers one question, over and over: *given what is on disk right now, what should be produced next, and what are the instructions for producing it?* The generating is the agent's job; the sequencing, gating and rollback bookkeeping is LoopSpec's.

## The problem it solves

Spec-driven development with an LLM tends to fail in three ways:

- **The agent skips ahead.** It writes an implementation plan before the requirements are settled, because nothing forced the ordering.
- **Review outcomes evaporate.** A security or human review says "no, because X"; two turns later the same X is back, because the objection was never durable state.
- **Progress drifts from reality.** A separate progress database says a step is done while the actual file was never written, or was written and then deleted.

LoopSpec addresses each one structurally rather than by prompting harder:

- Ordering is a declared dependency graph, so a node stays `blocked` until its inputs exist.
- Gate failures **move** the failed attempt into `.attempts/round-NNN/` and hand the next attempt the previous verdict's blocking issues, so an objection survives into the retry.
- There is no progress database. Every status, verdict and retry count is derived from the filesystem on every call.

## Core model

### Everything is derived from the filesystem

LoopSpec stores no state of its own beyond the files you can see. On every command it walks the [workflow home](#glossary), reads which artifacts exist, reads gate verdict files, counts `.attempts/round-NNN/` directories, and derives everything from that. There is nothing to get out of sync, and repairing a confused workflow means moving or deleting a file rather than editing a database.

Each node ends up in exactly one of five statuses:

| Status | Meaning |
| --- | --- |
| `blocked` | At least one required node is not `done` yet. |
| `ready` | Dependencies are satisfied and the output does not exist yet — this is the work to do. |
| `done` | The output exists (and, for a gate, is a PASS; and, if the node declares `tracks`, every tracked checkbox is ticked). |
| `failed` | A gate whose FAIL output exists and which still has retries left. Roll back to continue. |
| `exhausted` | A gate that has failed and used up `max_retries`. No further rollback is possible. |

### Nodes, artifacts and gates

A plain node declares `generates` (the artifact path it is responsible for) and a `template`. It is `done` once that path exists. `generates` may be a glob such as `specs/**/*.md`, in which case any match counts.

A [gate](#glossary) node declares two output paths instead — one for PASS, one for FAIL — and an `on_fail` policy. Writing the PASS file means the gate passed; writing the FAIL file means it failed. Writing both is an error (`gate_output_conflict`), because then the verdict is ambiguous.

### Rollback moves, never deletes

When a gate fails, `loopspec rollback` computes the **reset closure**: the nodes named in `on_fail.reset`, the gate itself, and every transitive dependent of those. It then *moves* each of those nodes' artifacts into `.attempts/round-NNN/`, bumping `NNN` for each round. Nothing is deleted, so the next attempt can be shown exactly what the previous one produced and why it was rejected — that is what the `priorAttempts` field of `loopspec instructions` carries.

### The driving loop

Two commands do almost all the work. `loopspec status` reports every node's status and a `nextSteps` list naming the single command to run next; `loopspec instructions <node>` returns the prompt, template, dependency paths and prior failures for one node. An agent alternates between them until the change is complete. See [Agent protocol](agent-protocol.md) for the field-by-field contract, and [CLI reference](cli-reference.md) for every command.

## Where things live on disk

```text
<project root>/
  loopspec/                       # the workflow home (default ./loopspec)
    config.yaml                   # which schema to use, and project-wide extras
    schemas/
      secure-spec-driven/         # a schema: node graph + templates + instructions
        schema.yaml
        templates/
        instructions/
    changes/
      add-payment/                # one change
        .workflow.yaml            # which schema this change was created with
        state.md                  # the change's working memory
        proposal.md               # artifacts, as declared by the schema
        design.md
        specs/<capability>/spec.md
        tasks.md
        security/pass.md
        .attempts/round-001/      # artifacts moved here by a rollback
    archive/
      2026-07/add-payment/        # completed changes, moved here by `archive`
  .claude/                        # optional agent skills/commands, written by `init`
```

`state.md` and `.workflow.yaml` are reserved: a schema may not declare either of them as a node output. `state.md` is the one file a rollback never touches, which makes it the only place where intent survives across rounds.

## What LoopSpec does not do

- It does not call an LLM. It emits instructions; something else does the generating.
- It does not run your tests, edit your code, or approve anything on a human's behalf.
- It does not revert code. Rollback archives artifact files inside the change directory; a line of source code that an implementation node already wrote stays written.

## Glossary

Terms used across the rest of the manual.

| Term | Meaning |
| --- | --- |
| **workflow home** | The directory holding `config.yaml`, `schemas/`, `changes/` and `archive/`. Defaults to `./loopspec`; every command takes `--home` to point elsewhere. |
| **project root** | The parent of the workflow home — where agent tool directories (`.claude`, `.codex`, ...) are written, because that is where those tools look. |
| **schema** | A YAML description of one workflow: its nodes, their dependencies, artifact paths, templates and gate policies. Lives in `<home>/schemas/<name>/schema.yaml`. |
| **change** | One unit of work moving through a schema. Lives in `<home>/changes/<name>/`, named in kebab-case. |
| **node** | One step in a schema. Either a plain node (produces an artifact) or a gate (produces a verdict). |
| **artifact** | A file a node is responsible for producing, named by `generates` relative to the artifact root. |
| **artifact root** | Where a change's artifacts live. The change directory itself, unless the schema is referenced with a `path` in `config.yaml`, which nests them in a subdirectory. |
| **gate** | A node that produces a PASS or FAIL verdict rather than a document, plus a policy for what to redo on FAIL. |
| **verdict** | The PASS or FAIL outcome of a gate, recorded by which of its two output files exists. |
| **reset closure** | The set of nodes a rollback resets: `on_fail.reset`, the failing gate itself, and all transitive dependents, in topological order. |
| **attempts round** | One `.attempts/round-NNN/` directory holding the artifacts a single rollback moved aside, plus a `_meta.yaml` recording the verdict that caused it. |
| **tracked node** | A node declaring `tracks: <file>`, which is only `done` once every checkbox in that file is ticked. |

## Next

- [CLI reference](cli-reference.md) — every command, flag and JSON field.
- [Configuration](configuration.md) — `config.yaml`, field by field.
- [Schema reference](schema-reference.md) — how to write your own workflow.
- [Agent protocol](agent-protocol.md) — the loop an LLM agent should run.
- [secure-spec-driven](workflows/secure-spec-driven.md) — the built-in workflow.
