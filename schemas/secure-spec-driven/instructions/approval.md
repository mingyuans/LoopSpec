Summarize the whole plan for a human, get their explicit decision, and record it
as a PASS or FAIL verdict.

This is a gate: you must write to exactly one of the two output paths. Unlike
every other node in this schema, the verdict here is not yours to make - it is
whatever the human answers.

## 1. Read everything first

Read every file listed in `contextFiles` (proposal, specs, design, tasks, and
the security verdict). Do not summarize from memory or from filenames.

## 2. Summarize for a human, not for a model

Present a summary that a person can review in a couple of minutes. Cover:

- What problem this change solves and why it is worth doing now
- Which capabilities are added or modified
- The key technical decisions and what was traded away for each
- The size and ordering of the task list (how many tasks, what happens first)
- The security review's conclusion and any residual risk it accepted

Name concrete artifacts and paths. Call out anything you had to guess, and any
open question the human is better placed to answer than you are.

## 3. Ask the human to decide

Use your host tool's interactive question facility - Claude Code's
`AskUserQuestion` tool, or the equivalent mechanism in whatever tool you are
running under - to ask for a clear choice between:

- proceed with this plan as written, or
- adjust it first (and what specifically needs to change)

## 4. Write the verdict

- Human approves: write the pass output using the pass template.
- Human asks for changes: write the fail output using the fail template. Turn
  each request into one discrete, self-contained bullet under "Changes
  Requested" - each bullet becomes an item the next attempt must resolve.

A FAIL rolls the change back and redoes `specs`, `design`, and `tasks`; the
human's requests are handed to those nodes as `priorAttempts`, so write them so
they are actionable without this conversation.

**Never approve on the human's behalf.** If you have no way to ask a human, or
the human has not answered yet, write *neither* output and stop here, reporting
that this change is waiting on human approval. The node stays `ready` - that is
the correct state for "waiting on a person", and a fabricated PASS would defeat
the entire point of this gate.

## 5. Record the verdict in state.md

After writing the verdict file, append the decision to `state.md` (the path is
in `statePath`; its current contents are in `state`). Let N be the number of
`priorAttempts` entries for this gate, plus one - that is this round's number.

- `Decision Log`: one entry with the round number, the outcome (approved /
  changes requested), the **distilled** decision points, and the path of the
  verdict file.
- `Frozen Decisions` (on approval): the plan points the human signed off on,
  noting that later nodes must not quietly change them - changing them requires
  another approval round.
- `Rejected Options` (on changes requested): the approaches the human ruled out.
- `Open Questions` (on changes requested): what the human raised without
  settling it.
- `Current Focus` (on changes requested): rewrite to "redo specs/design per
  round N feedback".
- `Artifact Notes`: the verdict file's path and outcome.

**Append only.** Never delete or reword existing entries. `state.md` is not any
node's artifact, so rollback never archives it - it is the only place where the
human's intent survives across rounds, and it has no `.attempts/` history to
recover from if you overwrite it.

If `warnings` contains `state_missing`, recreate `state.md` with the standard
sections (`Current Focus`, `Frozen Decisions`, `Decision Log`,
`Rejected Options`, `Open Questions`, `Artifact Notes`) before appending.

### What goes where

The human's **verbatim words** belong in the verdict file, not in `state.md`.
`state.md` gets the distilled points plus the path to the verdict file, so
anyone who wants the exact wording can go read it there.

### Every state.md entry must stand on its own

Replace every pronoun and deictic reference from the human's words - "this",
"that", "it", "the one above", "the thing you just said", "here" - with what it
actually refers to: a capability name, a file path, a task number, a requirement
name, a decision id.

- Bad: `- Skip this one for now, and that needs tests.`
- Good: `- Defer the CSV export capability (was task 3.2); add tests for
  src/billing/invoice.py.`

Later nodes read `state.md` without any of this conversation's context. An entry
that still contains "this" or "that" is worse than no entry: it looks like
information but cannot be resolved.

When distilling, keep the human's qualifiers and exceptions intact ("fine, but X
has to land first" must not become "fine"). The verbatim quote in the verdict
file is your backstop if the distillation turns out to have lost something.
