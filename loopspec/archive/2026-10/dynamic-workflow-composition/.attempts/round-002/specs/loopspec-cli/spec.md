## ADDED Requirements

### Requirement: Composition command groups
The CLI SHALL expose `fragments`, `compose`, `recompose`, `plans`, and `profiles` surfaces described by the composition capabilities. Every command SHALL support `--json`, use the common `{error,message,fix}` failure envelope, and avoid embedding request prose or approval text into generated shell commands.

#### Scenario: JSON validation response
- **WHEN** `loopspec compose validate <request> --json` succeeds
- **THEN** stdout is one JSON document containing `valid`, `planDigest`, `requiresApproval`, `readyToApply`, selected fragments, omissions, nodes, and build order

#### Scenario: Composition failure
- **WHEN** any composition command rejects untrusted input
- **THEN** it exits 1 and returns the common structured error contract without a traceback

### Requirement: Existing command responses identify active plans
For plan-backed changes, `new` and `status` JSON SHALL add `planRevision`, `planDigest`, and `selectedFragments`; legacy changes SHALL return these fields as null or an empty list without changing existing fields. Instructions and rollback behavior SHALL continue to consume the same active `LoadedSchema` selected by the shared change-context resolver.

#### Scenario: Status composed change
- **WHEN** status is run on a composed change
- **THEN** the response identifies its active revision and digest while preserving all existing node/status fields

#### Scenario: Status legacy change
- **WHEN** status is run on a legacy schema change
- **THEN** existing fields and next-step semantics remain unchanged

### Requirement: New composition error codes
The CLI SHALL document and emit distinct errors for missing/invalid fragments, invalid composition requests, protected-gate approval requirements, plan materialization failure, stale plan revision, unsafe recomposition, missing profile, and profile conflict.

#### Scenario: Agent receives actionable correction
- **WHEN** a composition request is rejected
- **THEN** its error code distinguishes the violated invariant and `fix` identifies the exact next corrective action

### Requirement: Initialization includes composition directories
`loopspec init` SHALL create `fragments/` and `profiles/` and copy packaged built-in fragments unless `--no-builtin` is set. Existing `schemas/`, `changes/`, config, and tool-scaffolding behavior SHALL remain compatible.

#### Scenario: No-builtin initialization
- **WHEN** `init --no-builtin` is run
- **THEN** empty fragments and profiles directories exist and no packaged fragment is copied

### Requirement: Documentation and JSON contract consistency
English and Chinese CLI, configuration, schema, overview, agent-protocol, and workflow documentation SHALL describe composition and recomposition consistently. Documentation tests SHALL cover command names, fields, error codes, built-in fragments, and bilingual parity.

#### Scenario: Documentation drift
- **WHEN** a composition command, field, error code, or built-in fragment changes without corresponding documentation updates
- **THEN** the documentation consistency test fails
