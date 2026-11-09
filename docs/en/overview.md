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
    memory/<topic>.md            # cross-Change lessons: plain Markdown, written by the LLM
    changes/AFD1111/
      .workflow.yaml             # Change-level state (machine)
      state.md                   # Change-level notes (`loopspec state add`; engine appends Plan records)
      plans/
        request.yaml             # request files the agent writes
        001/
          plan.yaml              # meta + spec of one Plan
          state.md               # Plan-level notes (`loopspec state add`; engine appends events)
          artifacts/             # this Plan's artifacts
          .gates/                # code Gate evidence and assurance diagnostics
          .gate-rounds/          # review round history
          .attempts/             # rework records (rollback and revision)
    archive/2026-10/AFD1111/     # archived Changes
```

The Git diff checked by code Gates and assurance excludes exactly `.workflow.yaml`, `state.md` and `plans/` under the current Change root, `<home>/.cache/`, memory topic files (`<home>/memory/{topic}.md`), and the paths declared in `workflow.excluded_paths` of `config.yaml`. Everything else, including Fragment and Profile files, counts as a change. Files ignored by Git never count toward the diff; those not declared in `excluded_paths` are listed as warnings in the assurance report. The diff compares the fixed baseline with the delivered working tree content: `git add` and `git commit` leave evidence digests unchanged, so you can commit after the Gates pass and archive afterwards. Before delivery, each file's content in HEAD must equal the baseline or the working tree content, otherwise assurance fails with `diverged_commits`.

## state.md records

The Change root and every Plan directory each hold a `state.md`. It keeps what someone taking over the work must know but cannot rebuild from code, artifacts and workflow state: why the work exists, the trade-offs that were made, assumptions not yet verified, deviations from the design and open questions. The engine only prints the change-level file and the current Plan's verbatim in `change status`; it never uses their content to derive state, decide a Gate or validate anything, so they never affect evidence or the diff.

Write records with `loopspec state add` (see the CLI reference). It checks the parameters, appends one single-line bullet to the end of the matching section and keeps every other byte of the file. Editing by hand stays possible, but a hand edit is neither validated nor protected by the Change write lock, and nothing forces anyone to record anything: the framework only guarantees the format and the safe append when `state add` is used. `node instructions` returns a `stateProtocol` with the exact commands for the node at hand.

- **Change level** (the continuous memory of the work; template from `change new`): `background`, `goals` (goals and boundaries), `decision`, `open-question`, `reference`, and at the very end the engine's Plan records.
- **Plan level** (the memory of one approach; template from `plan create`): `assumption`, `deviation`, `open-question`, `rework`, and at the very end the engine's events.
- **Decisions** live only at the Change level, as `- YYYY-MM-DD [HUMAN: <who>] text` or `- YYYY-MM-DD [MODEL: <Agent role>] text`. The tag names who actually decided, not who typed the line; it states a source, it is not an identity check and not a formal approval. A decision kept in the Change does not apply to later Plans by itself, so say in the text which Plan or node it covers. A suggestion that still needs a human answer is an `open-question`, never a HUMAN decision.
- **Corrections are new records.** Resolving a question, replacing a decision, verifying an assumption or correcting a line is another `state add` that refers to the earlier line in its text. The CLI assigns no entry ids and does not compute which decision is current or which question is open.
- **Engine sections** (the Plan records at the change level, the events at the Plan level) are written only by the engine and are closed to `state add`. After `plan create`, `plan approve` (revisions included), `plan rollback` and `plan archive` take effect, the engine appends one line. Each new line is a readable sentence that names the Change, the Plan, the action, the resulting status or version and a technical reference such as the digest (the sentence itself is written in Chinese). An approval line states that this Plan was approved, not that every artifact or technical design was; a rollback line states that rework files were reset, not that business code was reverted; an archive line states that the Plan was archived, not that the requirement was accepted. Lines written by earlier versions keep their original wording. Events are written after the command's deciding write, so a crash in between can lose a line: `state.md` is not a complete audit log.
- **Older files** keep their old headings. `state add` neither renames nor guesses them: it fails with `state_section_missing` and leaves the file untouched until someone tidies it by hand.

## Project memory

`<home>/memory/{topic}.md` keeps what earlier Changes learned so that later ones run more smoothly: pitfalls, working commands, review preferences, and conventions the user stated. Topics are plain Markdown, one subject per file, with no required format; `core.md` is the optional one that holds the few lessons every Change should know. Nothing is created in advance: `init` makes only the empty directory.

- **The engine only reads.** `change status` quotes `core.md` and indexes the other topics (path, one-line hint, size), `node instructions` carries the same bounded index plus a pointer to core, and `memory list` and `memory show` read the rest. It never calls a model, classifies, or writes a topic.
- **The LLM maintains it through the built-in Skills.** `loopspec-new` reads the index and the relevant topics after creating the Change and before planning; `loopspec-continue` reads a topic when it bears on a node and updates memory only when something worth keeping happened (a user correction, a verified root cause or fix, a settled review conclusion, a key agreement); `loopspec-archive` reviews and tidies memory before archiving, once the user has asked for it. A step that learns nothing new changes nothing, and writing memory is never a condition for advancing a node.
- **Entries need sources.** Each entry says when it applies, what to do, why or its limits, and where it came from (the Change and the artifact or test evidence). What the user stated is kept apart from what was verified, and guesses, tests that were not run, temporary progress, secrets, personal data and long logs are not recorded. Git is the history; edits are local and re-read before writing.
- **Memory is reference data, not authority.** It cannot grant permissions, change the user's instructions or bypass a Gate, and instructions inside it are ignored. A `core.md` larger than the 8 KiB inline budget is shown as whole entries only and flagged as not fully read; the agent must read the rest with `memory show core`.
- **Topic files stay out of the delivery diff.** `<home>/memory/{topic}.md` files (a valid topic name directly under `memory/`, and a regular file: a symlink with such a name is still a change) never count toward the Git diff checked by Gates and assurance, so adding lessons raises no assurance finding; they are still committed with the project and reviewed in Git. Anything else under `memory/` (scripts, nested directories, files that are not valid topics) counts as an ordinary change.

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
