## 1. Composition Domain Models and Errors

- [ ] 1.1 Add strict Pydantic models for fragment manifests, node references, composition requests, omission approvals, plan manifests, profiles, and extended workflow metadata.
- [ ] 1.2 Add structured error types for fragment lookup/validation, composition validation/approval, plan materialization, stale revision, unsafe recomposition, and profile lookup/conflict.
- [ ] 1.3 Add safe path, bounded single-read, canonical serialization, and atomic-write helpers used by every composition command.

## 2. Fragment Catalog and Built-in Resources

- [ ] 2.1 Implement fragment discovery, strict loading, source-schema/node resolution, deterministic listing, and per-fragment validation.
- [ ] 2.2 Add output ownership collision checks and strict-additive duplicate attribution.
- [ ] 2.3 Add seven packaged fragment manifests over `secure-spec-driven`, marking security-review and approval protected.
- [ ] 2.4 Extend built-in resource lookup and `init` to create fragments/profiles and copy missing built-in fragments safely.
- [ ] 2.5 Add fragment catalog unit and CLI tests, including traversal, symlink escape, unknown fields, identity mismatch, and source failures.

## 3. Static Composition Compiler — Version 1

- [ ] 3.1 Implement safe workflow-home-relative composition request loading and strict inclusion/omission reason validation.
- [ ] 3.2 Resolve selected fragments, source nodes, instructions, and templates exactly once into a contained in-memory bundle; namespace resource destinations and reuse the existing loader for complete-graph validation.
- [ ] 3.3 Implement canonical SHA-256 plan digests covering effective schema, rationale, and every buffered resource destination/length/content hash; use the same bundle for approval checks and writes.
- [ ] 3.4 Implement protected-fragment omission approval checks against the full content-bound digest.
- [ ] 3.5 Implement self-contained plan staging, buffered resource writes, manifest hash verification, post-copy validation, atomic directory activation, and atomic metadata replacement.
- [ ] 3.6 Extend the shared change-context resolver to load active plan snapshots while retaining legacy schema behavior.
- [ ] 3.7 Add `compose validate` and composition-aware `new`, including mutually exclusive option handling and JSON contracts.
- [ ] 3.8 Add static composition tests for digest/resource stability, stale approval, graph failure, atomic failure, source mutation isolation, and full legacy regression coverage.

## 4. Recomposition and Plan History — Version 2

- [ ] 4.1 Implement active plan inspection and immutable revision history loading.
- [ ] 4.2 Implement frozen-node discovery from current states, cursor position, and all attempts metadata.
- [ ] 4.3 Implement semantic frozen-node comparison including resource hashes, ahead-of-cursor enforcement, base-revision concurrency checks, and protected-gate revalidation.
- [ ] 4.4 Implement atomic `recompose` activation with predecessor digest and revision summary.
- [ ] 4.5 Add `plans show` and `plans history` commands with safe contained reads.
- [ ] 4.6 Add recomposition tests for completed/current/attempt-history freezes, safe future changes, stale revisions, failed activation, and protected-gate removal.

## 5. Project Fragments and Reusable Profiles — Version 2

- [ ] 5.1 Verify project-authored fragments use the same catalog and validation path as packaged fragments.
- [ ] 5.2 Implement profile save/load/list/show with safe names, deterministic serialization, conflict handling, and no persisted approval text.
- [ ] 5.3 Implement `new --profile` with current-source recompilation and per-change approval overlay behavior.
- [ ] 5.4 Add profile tests for reuse, changed sources, unsafe names, conflicts, and mandatory fresh approval.

## 6. CLI Integration and Presentation

- [ ] 6.1 Register fragments, compose, plans, and profiles Typer groups plus top-level recompose.
- [ ] 6.2 Add active plan fields to new/status responses while preserving legacy fields and default output behavior.
- [ ] 6.3 Add concise human-readable summaries for new composition commands without exposing raw Python containers.
- [ ] 6.4 Extend error, response-field, and command-surface consistency tests.

## 7. Skills and Documentation

- [ ] 7.1 Update packaged loopspec-new and loopspec-continue skills for safe request files, validation, protected-gate judgement, and explicit recomposition.
- [ ] 7.2 Regenerate or update checked-in LoopSpec tool projections without overwriting unrelated user-installed AI-DLC files.
- [ ] 7.3 Update English overview, agent protocol, configuration, schema/workflow, and CLI reference documentation.
- [ ] 7.4 Apply matching Chinese documentation changes and extend bilingual drift checks.

## 8. Verification

- [ ] 8.1 Run focused composition, CLI, security, and compatibility tests and resolve failures.
- [ ] 8.2 Run the complete pytest suite.
- [ ] 8.3 Run ruff and mypy.
- [ ] 8.4 Exercise a temporary workflow home end to end: composed new, protected omission approval, status/instructions, future-only recomposition, profile save/reuse, and legacy new.
- [ ] 8.5 Review the final diff for path safety, untrusted-input handling, documentation consistency, and accidental changes to unrelated work.
