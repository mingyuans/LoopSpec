# secure-spec-driven

> Scope: the built-in workflow — its seven nodes, what each one must produce, and why each gate resets what it resets.
> Audience: humans and LLM agents working a change through the default workflow.
> Language: **English** · [中文](../../zh/workflows/secure-spec-driven.md)

`secure-spec-driven` is the schema `loopspec init` installs and `config.yaml` defaults to. It takes a
change from "why are we doing this" to "the code is written and the tests pass", with a security
review, a human sign-off and an implementation step as [gates](../overview.md#glossary).

## The node graph

```text
proposal ──┬──> specs ──┐
           └──> design ─┴──> tasks ──> security ──> approval ──> apply
```

| Node | Type | Requires | Output |
| --- | --- | --- | --- |
| `proposal` | plain | — | `proposal.md` |
| `specs` | plain | `proposal` | `specs/**/*.md` |
| `design` | plain | `proposal` | `design.md` |
| `tasks` | plain | `specs`, `design` | `tasks.md` |
| `security` | gate | `tasks` | `security/pass.md` or `security/fail.md` |
| `approval` | gate | `security` | `approval/approved.md` or `approval/changes-requested.md` |
| `apply` | gate | `approval` | `apply/report.md` or `apply/blocked.md` |

`apply` also declares `tracks: tasks.md`, so it is only `done` once every checkbox in `tasks.md` is
ticked. Every node loads its instruction text from `instructions/<node>.md`, and every gate ships a
template for both verdicts.

Because `specs` and `design` both depend only on `proposal`, they are `ready` at the same time. The
order you write them in does not matter; `tasks` waits for both.

## The nodes

### proposal

Establishes **why**. Sections: `Why`, `What Changes`, `Capabilities`, `Impact`.

The `Capabilities` section is load-bearing: it is the contract between this node and `specs`. Every
new capability listed there becomes one `specs/<name>/spec.md`, and every modified capability needs a
delta spec against the existing one. Research the project's existing specs before filling it in;
inventing a capability name here produces an orphan spec file later.

Keep it to one or two pages, and keep implementation detail out — that is `design`'s job.

### specs

Defines **what** the system should do: one spec file per capability the proposal listed, at
`specs/<capability>/spec.md`.

Format rules that the tooling depends on:

- Each requirement is `### Requirement: <name>` followed by normative text using SHALL or MUST.
- Each scenario is `#### Scenario: <name>` with `- **WHEN**` / `- **THEN**` bullets.
- Scenarios need exactly four hashes. Three hashes or a bullet list fails silently.
- Every requirement needs at least one scenario. Each scenario is a potential test case.

Deltas against existing specs use `## ADDED Requirements`, `## MODIFIED Requirements`,
`## REMOVED Requirements` and `## RENAMED Requirements`. A MODIFIED requirement must carry the entire
updated requirement block, not just the changed sentence — partial content loses detail permanently.
REMOVED needs a `**Reason**` and a `**Migration**`.

### design

Explains **how**, and only when the change warrants it: a cross-cutting change, a new architectural
pattern, a new external dependency, a significant data model change, security or performance or
migration complexity, or genuine ambiguity worth settling before coding.

Sections: `Context`, `Goals / Non-Goals`, `Decisions`, `Risks / Trade-offs`, `Migration Plan`,
`Open Questions`. Each decision should name the alternatives considered and why they lost — the "why"
is the part that survives usefully.

One practical note: the `security` gate reads this file. Call out anywhere the design touches
authentication, authorization, input handling, secrets or external integrations, because those are
exactly what the review will look for.

### tasks

Breaks the work into a checklist. Format matters — progress tracking parses it:

- Group tasks under `## <number>. <group name>` headings.
- Every task is a checkbox: `- [ ] X.Y Description`.
- A line that is not a checkbox is not tracked.
- Order tasks by dependency; the order encodes what must happen first.
- Each task should be small enough to finish in one sitting and verifiable enough that you know when
  it is done.

The `security` gate reads this file too, so make any task touching authentication, authorization,
external input, secrets or third-party dependencies easy to spot.

### security

The first gate. Reviews `design.md` and `tasks.md` and writes exactly one of `security/pass.md` or
`security/fail.md`.

What it checks: injection risks from untrusted input, authentication and authorization gaps, secrets
handling, path traversal, unsafe deserialization, new third-party dependency risk, and data exposure.

On FAIL, each bullet under `Blocking Issues` becomes one entry in the next attempt's `priorAttempts`,
so each bullet must be self-contained and actionable — one concrete issue per bullet, not a paragraph.
On a retry, verify that each previously listed issue was actually addressed; a rewording that leaves
the risk in place must not pass.

| Setting | Value | Why |
| --- | --- | --- |
| `reset` | `[design]` | A security finding is almost always a "how" problem. Resetting `design` also resets `tasks` and the gate itself through the closure, so the plan is rebuilt from the decision that caused the problem. `specs` survives, because *what* is being built is rarely what the review objected to. |
| `max_retries` | `3` | Enough for a couple of genuine iterations; beyond that the design likely has a structural problem a human should look at. |
| `on_exhausted` | `escalate` | Hand off to a human rather than stopping silently. |

### approval

The human sign-off gate — the only node whose verdict is not the agent's to make.

The agent reads every artifact produced so far, summarises the plan for a person in a couple of
minutes' reading, and asks for an explicit choice using its host tool's interactive question facility.
Approved writes `approval/approved.md`; changes requested writes
`approval/changes-requested.md`. Either way the verdict is recorded in `state.md`, distilled and
de-pronouned, with the human's verbatim words kept in the verdict file.

The agent is told never to approve on the human's behalf. With no way to reach a human the node simply
stays `ready` and waits, which is the correct state for "waiting on a person".

| Setting | Value | Why |
| --- | --- | --- |
| `reset` | `[specs, design]` | Human feedback at this point routinely touches *what* is being built, not just *how*, so both are redone. |
| `max_retries` | `5` | Higher than the security gate: rounds of human feedback are normal and cheap compared with rebuilding an implementation. |
| `on_exhausted` | `escalate` | Five rejected plans is a conversation to have, not a loop to keep running. |

### apply

The implementation gate, and the only node that touches source code.

The agent reads every artifact — `contextFiles` in the `instructions` response hands it the real paths
— works through `tasks.md` ticking checkboxes as it goes, runs the project's tests and checks, and
writes `apply/report.md`. The report is the only account of what the change did to the codebase, so it
lists the files touched, the real test output, and any deviation from the design along with why.

If the plan itself turns out to be unworkable, it writes `apply/blocked.md` instead. That report must
record the code changes already made: rollback archives artifact files inside the change directory and
does not revert a single line of code, so without that record the next round plans against a working
tree nobody has described.

Because of `tracks: tasks.md`, writing the report early does not finish the node: `apply` stays
`ready`, `isComplete` stays `false`, and `loopspec archive` keeps refusing with `archive_unsafe`.

| Setting | Value | Why |
| --- | --- | --- |
| `reset` | `[design]` | An implementation blocker is almost always a "how" problem. A genuine "what" problem gets caught again by the `approval` gate downstream, which sits between `design` and `apply`. |
| `max_retries` | `2` | Lowest of the three: reworking a partly-built implementation is the most expensive kind of retry. |
| `on_exhausted` | `escalate` | Two failed implementation attempts means a human should look at the plan. |

## Walking a change through it

```bash
loopspec new add-payment --json
loopspec status add-payment --json
loopspec instructions proposal --change add-payment --json
# write proposal.md, update state.md, then loop back to status
```

`status` names the next node every time, so the sequence takes care of itself: `proposal`, then
`specs` and `design` in either order, then `tasks`, then the three gates. If `security` or `approval`
fails, `status` hands you a `pendingRollback` command; run it and redo the reset nodes with
`priorAttempts` in hand. When `isComplete` turns `true`:

```bash
loopspec archive add-payment --json
```

## Next

- [Agent protocol](../agent-protocol.md) — the loop in field-by-field detail.
- [Schema reference](../schema-reference.md) — how to modify this schema or write your own.
