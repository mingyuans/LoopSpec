# Overview

> Scope: what LoopSpec is, its two hierarchies, the derived statuses, the disk layout and the glossary.
> Audience: humans and LLM agents, first page to read.
> Language: **English** · [中文](../zh/overview.md)

## What LoopSpec is

LoopSpec is a command-line tool that keeps an LLM agent on a plan a human confirmed. It does not generate anything itself. On every call it answers: *given what is on disk now, which node of the confirmed Plan runs next, and with which instructions?* Writing documents and code is the agent's job; sequencing, Gates, rework bookkeeping and the final assurance check are LoopSpec's.

It addresses the usual failure modes of agent-driven delivery structurally:

- **Skipping ahead.** Execution follows a confirmed dependency graph; a node stays `blocked` until its inputs are done.
- **Unconfirmed plans.** Every Plan, every revision and every replan becomes effective only with the digest of what a human was shown.
- **Unreviewed code.** Code Gates record evidence bound to the exact files reviewed; the final assurance node checks the full Git diff since the Change's fixed baseline.
- **Forgotten objections.** A failed Gate's report is archived with the rework and handed to the redo as `priorAttempts`.
- **Drifting progress.** There is no progress database: node status is derived from files on every call.

## Two hierarchies

**Task hierarchy - Change, Plan, Revision.** A *Change* is one piece of work (usually a ticket). It holds any number of *Plans* over time, but at most one is open (draft or approved). A Plan is improved in place by *Revisions*; when the task itself changes, the Plan is archived with the human's consent and a new Plan is drafted from an empty state.

**Workflow hierarchy - Node, Fragment, Profile, Plan.** A *Node* is one executable step (an artifact or a Gate). A *Fragment* is a reusable group of nodes that may reference other Fragments. A *Profile* is a reusable `flow` of Fragment instances, used as a template. A *Plan* is the concrete graph for one Change: its `spec` records the agent's `flow` and the fully expanded leaf `nodes` the CLI executes.

## Statuses

A Change's status is derived from its Plans; nothing about it is stored:

| Status | Meaning | Next step |
| --- | --- | --- |
| `unplanned` | No open Plan. | Draft a Plan with `plan create`. |
| `planning` | The open Plan is a draft. | `plan show`, human confirmation, `plan approve`. |
| `active` | An approved Plan that is not complete. | Follow `nextSteps`. |
| `complete` | Every node of the active Plan is done, assurance included. | `change archive`. |

Each leaf node of the active Plan is in one of five statuses:

| Status | Meaning |
| --- | --- |
| `blocked` | A required node is not `done` yet. |
| `ready` | Inputs are done and the output is missing or stale. |
| `done` | The artifact exists, or the Gate has a PASS with valid evidence. |
| `failed` | An effective FAIL whose Gate still has `on_fail` retries left; run `plan rollback`. |
| `exhausted` | An effective FAIL with no `on_fail` or no retries left; a human decides. |

A Plan's own `meta.status` records only human decisions: `draft`, `approved` or `archived`. The open Plan is the draft or approved one and the active Plan is the approved one; no pointer stores either. Completion is never stored; editing code after completion makes the derived status fall back to unfinished.

Every command takes effect in a single write. If one is interrupted, the Change is either as it was before or as the command left it, never in between, so an agent simply continues from `change status`.

## Where things live on disk

```text
<project root>/
  loopspec/                      # workflow home (default ./loopspec)
    config.yaml
    fragments/<name>/            # fragment.yaml plus its instructions and templates
    profiles/<name>.yaml
    changes/AFD1111/
      .workflow.yaml             # Change-level state (machine)
      state.md                   # Change-level notes (human)
      plans/
        request.yaml             # request files the agent writes
        001/
          plan.yaml              # meta + spec of one Plan
          state.md               # Plan-level notes (human)
          artifacts/             # this Plan's artifacts
          .gates/                # code Gate evidence and assurance diagnostics
          .gate-rounds/          # review round history
          .attempts/             # rework records (rollback and revision)
    archive/2026-10/AFD1111/     # archived Changes
```

The Git diff checked by code Gates and assurance excludes exactly `.workflow.yaml`, `state.md` and `plans/` under the current Change root, `<home>/.cache/`, and the paths declared in `workflow.excluded_paths` of `config.yaml`. Everything else, including Fragment and Profile files, counts as a change. Files ignored by Git never count toward the diff; those not declared in `excluded_paths` are listed as warnings in the assurance report.

## What LoopSpec does not do

- It does not call an LLM or run your tests; it hands out instructions and records results.
- It never moves, copies or deletes business code. Rework archives workflow files inside the Plan directory only.
- Local records do not authenticate anyone. A digest proves that what was approved is what was shown, not who approved it.

## Glossary

| Term | Meaning |
| --- | --- |
| **workflow home** | The directory holding `config.yaml`, `fragments/`, `profiles/`, `changes/` and `archive/`. Defaults to `./loopspec`; every command accepts `--home`. |
| **Change** | One piece of work, in `<home>/changes/<name>/`. Names use letters, digits, `_` and `-`, for example `AFD1111`. |
| **Plan** | One numbered plan of a Change, `plans/<NNN>/plan.yaml`. At most one is open at a time. |
| **active Plan** | The approved Plan; the only one execution commands touch. |
| **revision** | An in-place change of the approved Plan's `spec`, confirmed by digest. |
| **baseline** | The full commit hash fixed on the first `plan create`; every Plan of the Change diffs against it. |
| **Fragment** | A reusable group of nodes, in `fragments/<name>/fragment.yaml`. |
| **Profile** | A reusable `flow` template, in `profiles/<name>.yaml`. |
| **instance** | One use of a Fragment inside a flow, named by its path, for example `be` or `be/tests`. |
| **Gate** | A node whose result is a PASS or FAIL report instead of an artifact. |
| **code Gate** | A Gate with `evidence`: its verdict counts only with a recorded review round over the pinned code. |
| **assurance node** | The final Gate with `assurance`: the CLI checks the full diff against the rules and writes the verdict itself. |
| **on_fail** | A Gate's rework policy: which leaf nodes to reset and how many times. |
| **rework record** | `.attempts/<NNN>/record.yaml`, listing the files a rollback or revision archived. |
| **digest** | SHA-256 of a Plan `spec`; approval binds to it. |
