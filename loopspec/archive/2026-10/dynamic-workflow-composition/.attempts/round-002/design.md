## Context

LoopSpec currently loads one validated `schema.yaml` per change and hands the resulting `LoadedSchema` to status, instructions, rollback, and archive. Composition should add a deterministic compile boundary before those services, not replace them or introduce a progress database.

An LLM may select and explain fragments. LoopSpec alone resolves their schema nodes, validates the complete graph, buffers every resource, enforces protected-gate policy, calculates a content-bound digest, materializes an immutable revision, and activates it. Fragment YAML, custom schemas, request files, profiles, approval text, and paths are untrusted data.

## Goals / Non-Goals

**Goals:**

- Reuse validated schema nodes as declarative fragments.
- Compile a selected fragment set into a self-contained effective schema.
- Bind protected-gate omission approval to the exact graph and instruction/template bytes.
- Keep complete schemas and existing changes fully compatible.
- Permit only future, pending work to change during recomposition.
- Support project fragments and reusable profiles through the same validation path.
- Preserve filesystem-derived node, gate, retry, and task state.

**Non-Goals:**

- Calling an LLM or implementing numeric risk scoring in the CLI.
- Executable plugins, hooks, remote registries, arbitrary template code, or shell evaluation.
- Reordering or redefining completed work, reverting source code, or proving human identity.
- Replacing complete schemas, adding lifecycle phases, or adding an event-sourced progress store.

## Decisions

### D1. Fragment manifests reference existing schema nodes

Fragments live at `<home>/fragments/<name>/fragment.yaml` and declare `name`, positive `version`, `description`, optional `when`, `protected`, and one or more `{schema, id}` references. The name must match the containing directory. Source schemas are loaded through the existing strict loader and schema resolver.

This avoids duplicating node, gate, instruction, and template definitions. Copying full node definitions into fragments was rejected because those copies would drift. A separate global stage format was deferred because validated schemas already provide that catalog.

### D2. Requests are contained YAML data files

Composition requests are relative to the workflow home and contain:

```yaml
version: 1
fragments: [proposal, design, tasks, security-review, approval, implementation]
reasons:
  proposal: Establish intent before design
  design: Core loading and CLI behavior both change
omissions: {}
base_revision: null
```

Each selected fragment needs a non-empty reason. Each unselected protected fragment needs an omission reason. Approval is optional `{plan_digest, decision: approved, human_words}` data added only after the validator returns the digest.

Absolute paths, `..`, symlink escapes, unknown fields, unsafe names, and non-files are rejected. Reasons and human words never need shell interpolation. Arbitrary absolute request paths and command-line prose flags were rejected to keep the authority boundary and invocation safe.

### D3. Validation constructs one immutable resolved bundle

The compiler performs exactly one read of every selected fragment manifest, source schema, instruction, and template into a `ResolvedComposition` bundle. Each resource entry contains its namespaced destination path, raw bytes, and SHA-256 content hash. Paths are normalized and containment-checked before the read; size and UTF-8 validity are checked where the destination requires text.

The effective node definitions are rewritten to their namespaced resource destinations and validated as one schema. All later steps in the same operation—canonical digest generation, approval checking, and materialization—consume this in-memory bundle. They never reopen a source resource. This removes the validation/materialization substitution window identified by security review round 1.

### D4. The plan digest binds structure, rationale, and resource bytes

Canonical digest input includes:

- effective schema data;
- selected fragment names, versions, source references, and inclusion reasons;
- protected-fragment omission reasons;
- for every copied resource, its destination-relative path, byte length, and SHA-256 content hash.

Canonical JSON uses sorted keys and stable list order. Approval data, timestamps, absolute source paths, and YAML formatting are excluded. The output is `sha256:<hex>`.

A proposal that omits a protected fragment returns `requiresApproval: true`, its digest, and `readyToApply: false`. Approval becomes valid only when it contains the same digest, `decision: approved`, and non-empty verbatim human words. Any structural, rationale, or resource-content change invalidates it. LoopSpec validates this binding but does not claim to prove speaker identity.

### D5. Plan revisions are self-contained and atomically activated

Extended metadata keeps legacy fields and adds an optional binding:

```yaml
schema: secure-spec-driven
created: 2026-10-05
plan: .workflow/plans/001
plan_revision: 1
plan_digest: sha256:...
```

Each immutable plan directory contains `schema.yaml`, `manifest.yaml`, and namespaced `instructions/` and `templates/`. Materialization writes only the buffered bytes from D3 into a contained staging directory, validates the finished schema and every manifest hash, then atomically renames the directory. Only afterward does it atomically replace `.workflow.yaml`. A failed operation cannot redirect the change to partial bytes.

When `plan` is absent, existing schema resolution is unchanged. When present, one shared change-context resolver safely resolves the plan inside the change and loads it with `load_schema()`. Downstream state and rollback services remain unchanged.

Recompiling from fragment names on every command was rejected because source edits would mutate active work. Storing progress in the plan was rejected because artifacts remain the source of execution truth.

### D6. Composition is strict-additive

Fragments add complete nodes only. Duplicate fragment names, duplicate node IDs, missing dependencies, cycles, invalid reset/tracking relations, missing resources, unsafe paths, concrete output collisions, and conservatively ambiguous output patterns fail with attribution. There is no patch or last-writer-wins operation. Node slug remains identity and topological order remains deterministic.

One compiler owns fragment resolution, graph validation, output ownership, protected policy, digesting, and materialization. CLI commands and skills consume its typed result rather than reimplementing these checks.

### D7. Built-in fragments project the existing secure schema

Seven built-in manifests reference the existing proposal, specs, design, tasks, security, approval, and apply nodes. Their public names are `proposal`, `specs`, `design`, `tasks`, `security-review`, `approval`, and `implementation`; security-review and approval are protected.

`init` copies missing manifests like it copies missing built-in schemas. The complete `secure-spec-driven` schema remains supported and serves as the built-in node source. No existing change is migrated.

### D8. Creation supports schema, composition, or profile paths

Legacy `loopspec new <change> [--schema <name>]` remains unchanged. `--composition <relative-request>` first builds the resolved bundle, validates approval, and only then creates the change and revision 1. `--schema`, `--composition`, and `--profile` are mutually exclusive.

A reusable profile supplies fragments, reasons, and omission reasons. If it omits a protected fragment, a per-change approval overlay must bind to the newly compiled digest; profiles never carry human approval forward.

### D9. Recomposition changes only future work

`recompose` requires `base_revision` equal to the active revision and a full replacement request. Frozen nodes comprise every done/failed/exhausted node, the first ready cursor and everything before it, and every node represented by attempts metadata or archived output ownership. Unreadable history causes refusal.

Frozen semantic definitions—including dependencies, outputs, instructions/templates by content hash, tracking, and gate policy—must remain equal. Additions/removals must be after the cursor and the replacement graph must independently validate. Protected policy is recalculated, so removing a pending protected gate needs new digest-bound approval.

An accepted operation materializes N+1 from one resolved bundle, records the predecessor digest and summary, preserves all earlier plan directories, and atomically updates only the metadata pointer.

### D10. Profiles preserve policy, not authority

`profiles save` writes a contained `<home>/profiles/<name>.yaml` with description, selected fragments, reasons, omission reasons, and source digest. It excludes approval and requires explicit overwrite for an existing name. On reuse, current sources are resolved again and the current digest is authoritative.

### D11. Skills remain thin

The new skill discovers fragments, writes a safe request file, validates it, and asks the human only for protected omissions. Continue still follows `status.nextSteps`; an explicit reshape request creates and validates a full replacement with the current base revision. Skills never edit metadata or plan snapshots directly and treat catalog prose as data, not executable instructions.

## Risks / Trade-offs

- **[Large resource bytes increase digest work]** -> Planning resources are small; apply explicit bounded reads and fail clearly when a configured limit is exceeded.
- **[Glob collision detection can be conservative]** -> Reject ambiguous ownership rather than guess.
- **[Approval provenance is host-limited]** -> Bind exact words and bytes to the digest and document that this is not identity proof.
- **[Concurrent recomposition]** -> Use base revision, exclusive final directory creation, and atomic metadata replacement.
- **[Project sources can be malicious or change concurrently]** -> Resolve contained paths, read each byte source once, hash the buffer, and write only that buffer.
- **[One release contains two increments]** -> Keep catalog/compiler isolated, land static composition first, then build recomposition/profile behavior on the same primitives.

## Migration Plan

1. Add strict composition models, errors, catalog loading, and resolved resource bundles.
2. Add canonical digesting, protected policy, built-in fragments, and init support.
3. Add atomic revision materialization, plan-backed context loading, compose validation, and composition-aware new.
4. Run all existing lifecycle tests against legacy and plan-backed changes.
5. Add frozen-node analysis, recomposition, and plan history.
6. Add profiles and profile-based creation.
7. Update skills and bilingual documentation, then run focused and full verification.

Rollback is a normal code rollback. Legacy changes remain readable. Composed changes keep complete snapshot directories; an older CLI will reject their additional metadata rather than misinterpret it.

## Open Questions

- None.
