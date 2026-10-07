## Context

LoopSpec currently loads one `schema.yaml` per change. The loaded schema owns node definitions and resource resolution, while status, instructions, rollback, and completion operate on the resulting `WorkflowGraph`. Change metadata stores only a schema name. This is a strong execution core, but schema selection is too coarse for tailoring a workflow to one request.

The new design inserts a composition boundary before that existing execution core. An LLM may choose and explain workflow fragments, but only LoopSpec may resolve fragment sources, validate the complete graph, enforce protected-gate policy, calculate a content digest, materialize resources, and activate a plan revision.

The input files, fragment manifests, approval text, and custom schemas are all untrusted. Every referenced name and path is validated before use; resource paths are resolved inside known roots; YAML is parsed as data; no fragment can execute a command.

## Goals / Non-Goals

**Goals:**

- Represent reusable fragments as declarative references to nodes in existing schemas.
- Compile selected fragments into a self-contained effective schema snapshot under the change.
- Bind protected-gate omission approval to the exact composition digest.
- Keep existing schema changes and commands working without migration.
- Support versioned recomposition of pending future work while freezing executed/current work.
- Support project fragments and reusable profiles without giving either an override path around validation.
- Keep all existing progress, gate, retry, and task state derived from visible files.

**Non-Goals:**

- Calling an LLM from LoopSpec or encoding numeric risk-scoring policy in the CLI.
- Executable plugins, shell hooks, arbitrary template code, or remote fragment registries.
- Reordering or rewriting completed work, reverting source code, or proving the identity of a person who supplied approval text.
- Replacing existing complete schemas or changing their runtime semantics.
- Adding an event-sourced progress database, multi-agent scheduler, or AI-DLC-style lifecycle phases.

## Decisions

### D1. Fragments reference schema nodes instead of copying node bodies

Fragments live under `<home>/fragments/<name>/fragment.yaml`:

```yaml
name: security-review
version: 1
description: Review the implementation plan for security risks
when: Include when code, configuration, trust boundaries, or external input changes
protected: true
nodes:
  - schema: secure-spec-driven
    id: security
```

A fragment may reference one or more nodes and may reference project-authored schemas. At compile time LoopSpec loads every source schema using the existing strict loader, copies the selected `NodeSpec` values, and copies their instruction/template resources into the effective snapshot using namespaced paths.

Alternatives considered:

- Copy complete node definitions into every fragment: rejected because templates, instructions, and gate policy would drift between schemas and fragments.
- Introduce an independent stage catalog immediately: rejected because existing schemas already provide a validated node catalog and compatibility source.

### D2. Composition requests are safe workflow-home-relative YAML files

A request has this shape:

```yaml
version: 1
fragments: [proposal, design, tasks, security-review, approval, implementation]
reasons:
  proposal: Establish intent before design
  design: The change crosses core loading and CLI boundaries
omissions: {}
base_revision: null
```

For every selected fragment, `reasons` contains a non-empty explanation. Every protected fragment not selected must appear in `omissions` with a non-empty reason. Approval is a separate optional mapping containing `plan_digest`, `decision: approved`, and the verbatim non-empty `human_words` supplied by the agent after asking the person.

Commands accept request paths relative to the workflow home and reject absolute paths, `..`, symlink escapes, non-files, unknown fields, and invalid names. This avoids embedding untrusted prose in emitted shell commands.

Alternatives considered:

- Passing reasons and human text as command-line arguments: rejected because it is error-prone across shells and encourages unsafe command construction.
- Reading arbitrary absolute request paths: rejected to keep path authority bounded to the workflow home.

### D3. Validation returns a digest before approval is supplied

`loopspec compose validate <request> --json` resolves fragments, builds the effective graph, validates all schema invariants, and returns:

- selected fragment metadata and per-fragment reasons;
- complete build order and node summaries;
- omitted protected fragments;
- `planDigest` calculated from a canonical JSON representation of the effective schema, selected fragment identities/versions, reasons, and omission reasons;
- `requiresApproval` and `readyToApply`.

Approval fields are deliberately excluded from digest calculation. A request omitting protected fragments can therefore be validated first, shown to the human with its digest, then updated with an approval binding to that digest. A mismatched digest, non-approved decision, missing words, or later plan edit makes it not ready to apply.

LoopSpec validates the record and binding but does not claim it can prove who typed the words.

### D4. Effective plans are immutable, self-contained schema snapshots

Composed changes retain `.workflow.yaml` but extend its strict model with:

```yaml
schema: secure-spec-driven
created: 2026-10-05
plan: .workflow/plans/001
plan_revision: 1
plan_digest: sha256:...
```

`schema` remains as provenance/base compatibility information. When `plan` is present, change loading resolves it safely inside the change and calls `load_schema()` on the materialized plan directory. Otherwise the existing schema path is used unchanged.

Each immutable plan directory contains:

- `schema.yaml`: the complete effective graph;
- `manifest.yaml`: selected fragments, versions, reasons, omissions, approval record, digest, revision, and predecessor digest;
- `instructions/` and `templates/`: namespaced resource copies required by the effective nodes.

Compilation writes a staging directory, validates the materialized schema, atomically renames it to its final revision path, then atomically replaces `.workflow.yaml`. A failed compile leaves the previously active plan intact.

Alternatives considered:

- Store only fragment names and recompile on every command: rejected because fragment/schema edits would mutate running changes.
- Embed runtime status in the plan: rejected because progress remains derived from artifacts.

### D5. Existing execution services consume `LoadedSchema` unchanged

`status`, `instructions`, `rollback`, `history`, and `archive` obtain their `LoadedSchema` through one change-context resolver. The resolver selects either the legacy schema directory or the current materialized plan. Downstream graph/state functions remain unchanged.

One implementation owns each invariant: the composition compiler owns fragment resolution, graph completeness, collisions, protected-gate policy, digesting, and plan materialization. CLI commands and skills consume compiler results rather than implementing parallel checks.

### D6. Composition is strict-additive and conflicts fail

Fragments contribute nodes; they do not patch existing nodes. Composition rejects:

- duplicate node IDs, including duplicates with unequal or equal definitions;
- missing dependencies, cycles, unsafe outputs, missing resources, invalid gates, invalid reset ancestors, and invalid tracking relations using the existing schema loader;
- concrete output collisions and ambiguous overlapping glob/concrete outputs;
- duplicate fragment selections, unknown fragments, source-schema/name mismatches, and fragment-name/file-name mismatches.

Node slug is identity; build/display order remains the deterministic topological order. There is no last-writer-wins behavior.

### D7. Built-in fragments are projections over the existing secure schema

Seven built-in fragments reference the existing seven nodes: `proposal`, `specs`, `design`, `tasks`, `security-review`, `approval`, and `implementation`. `security-review` and `approval` are protected. Initialization copies fragment manifests only when missing, just as it copies built-in schemas.

The existing `secure-spec-driven` schema remains a supported preset and the source for these fragments. Legacy changes require no migration.

### D8. `new` accepts either a legacy schema or a composition request/profile

The existing path is unchanged:

```text
loopspec new <change> [--schema <name>]
```

Composition adds mutually exclusive inputs:

```text
loopspec new <change> --composition <home-relative-request.yaml>
loopspec new <change> --profile <name> --composition <approval-overlay.yaml>
```

The profile form resolves its stored fragments/reasons/omissions and takes only a per-change approval overlay from the request. A profile retaining every protected gate can be used without an overlay. Creation refuses a non-ready request before writing a change directory.

### D9. Recomposition freezes present and historical execution evidence

`loopspec recompose <change> --composition <request>` requires `base_revision` equal to the active revision. It validates a full replacement plan, then compares it with the active plan.

Frozen nodes are:

- every `done`, `failed`, or `exhausted` node;
- the first `ready` node in deterministic build order (the current cursor);
- every node named in an attempts-round reset closure or owning archived files;
- every node preceding the current cursor.

Every frozen node must remain byte-equivalent in its semantic definition. New or removed nodes must be strictly after the cursor in the new graph. The new graph must independently pass all composition and protected-gate checks. Removing a pending protected gate requires an approval bound to the new digest.

Accepted recomposition materializes revision N+1, records the predecessor digest, and atomically moves only the metadata pointer. Previous plan directories remain readable audit history.

### D10. Profiles store selection policy, never reusable human approval

`loopspec profiles save <name> --change <change>` writes `<home>/profiles/<name>.yaml` containing selected fragments, reasons, omission reasons, description, and source digest. It never stores or reuses `human_words` or an approval binding.

Using a profile that omits a protected fragment therefore produces a new digest-bound approval requirement for the new change. Profile names and paths use the same safe kebab-case and containment rules as schemas/fragments.

### D11. Skills remain thin orchestrators

`loopspec-new` lists fragments, asks the LLM to author a composition request with inclusion and omission reasons, validates it, requests human judgement only when `requiresApproval` is true, and invokes `new` after `readyToApply` becomes true.

`loopspec-continue` continues to obey `status.nextSteps`; when the user asks to reshape remaining work, it authors a full request with `base_revision`, validates it, handles protected-gate confirmation if required, and invokes `recompose`.

The CLI never interprets requirement prose, and the skill never bypasses graph validation.

## Risks / Trade-offs

- **[Glob collision detection can be conservative]** -> Reject obvious concrete/concrete and glob/concrete overlaps; document that ambiguous glob/glob combinations are rejected rather than guessed.
- **[Schema resources may change after request validation]** -> Re-resolve and recalculate the digest inside `new`/`recompose`; materialize exactly the bytes that were digested.
- **[Approval provenance is host-limited]** -> Bind verbatim words to digest and state the trust boundary; never claim identity proof.
- **[Concurrent recomposition]** -> Require `base_revision`, use exclusive staging/final revision creation, and atomically compare/replace the active metadata pointer.
- **[Project fragments can reference unsafe schemas/resources]** -> Reuse strict schema loading and containment checks, and copy resources only after canonical containment verification.
- **[Large scope in one release]** -> Implement static composition first behind isolated modules/tests, then recomposition/profiles, while keeping legacy tests green throughout.
- **[Source schemas could later disappear]** -> Runtime uses self-contained snapshots; only new compositions need the source catalog.

## Migration Plan

1. Add composition models, catalog loading, validation, digesting, and materialization without changing existing new/status behavior.
2. Add built-in fragment resources and init copying.
3. Add compose inspection/validation and `new --composition`.
4. Route plan-backed changes through the shared change-context loader and run the existing lifecycle tests against composed plans.
5. Add recomposition, revision checks, frozen-node validation, and plan history inspection.
6. Add profiles and `new --profile`.
7. Update skills and bilingual documentation.

Rollback is code rollback: legacy `.workflow.yaml` remains readable, and every composed change contains a self-contained schema snapshot. Reverting the feature does not alter legacy changes, although a downgraded CLI will intentionally reject the new metadata fields rather than misread them.

## Open Questions

- None. The implementation may refine command spelling while preserving the specified JSON contracts and safety properties.
