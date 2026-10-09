## ADDED Requirements

### Requirement: Strict composition request
A composition request SHALL be a workflow-home-relative YAML file with `version: 1`, a unique non-empty `fragments` list, a non-empty reason for every selected fragment, an `omissions` mapping, optional approval data, and optional `base_revision`. Unknown fields, unsafe paths, invalid names, missing reasons, and reasons for unselected fragments SHALL be rejected.

#### Scenario: Complete request
- **WHEN** every selected fragment has one non-empty reason and all fields are valid
- **THEN** the request proceeds to graph compilation

#### Scenario: Missing inclusion reason
- **WHEN** a selected fragment has no corresponding reason
- **THEN** validation fails before any change or plan directory is written

#### Scenario: Unsafe request path
- **WHEN** `--composition` is absolute, contains `..`, or resolves outside the workflow home
- **THEN** the command fails without reading the external target

### Requirement: Complete effective graph validation
The compiler SHALL combine selected source nodes and apply all existing schema invariants to the complete graph, including unique IDs, existing dependencies, acyclicity, safe outputs, resource existence, gate reset ancestry, and tracked-file ancestry. It SHALL additionally reject concrete output collisions and conservatively reject ambiguous overlapping output patterns.

#### Scenario: Missing dependency after fragment selection
- **WHEN** `tasks` is selected without a fragment providing required node `design`
- **THEN** compilation rejects the request and identifies the missing dependency

#### Scenario: Output ownership collision
- **WHEN** two selected nodes can claim the same concrete artifact path
- **THEN** compilation rejects the request before materialization

### Requirement: Canonical plan digest
The compiler SHALL read every selected manifest, schema, instruction, and template exactly once into one validated in-memory bundle. It SHALL calculate `planDigest` as SHA-256 over canonical JSON containing the effective schema, selected fragment identities and versions, inclusion reasons, protected-fragment omission reasons, and for every materialized resource its destination-relative path, byte length, and SHA-256 content hash. Approval data, filesystem timestamps, absolute paths, and YAML formatting SHALL NOT affect the digest. Approval checking and materialization SHALL consume the same buffered bundle and SHALL NOT reopen source resources.

#### Scenario: Equivalent formatting
- **WHEN** two request files differ only in YAML formatting or mapping order
- **THEN** validation returns the same plan digest

#### Scenario: Material plan change
- **WHEN** a fragment version, node definition, selection reason, omission reason, instruction byte, or template byte changes
- **THEN** validation returns a different plan digest

#### Scenario: Source changes after bundle resolution
- **WHEN** a source resource changes on disk after the compiler buffered and hashed it
- **THEN** the current operation materializes the buffered bytes whose hash is in the digest; a later operation observes the new bytes and produces a new digest

### Requirement: Protected-fragment omission approval
Every catalog fragment marked protected SHALL either be selected or appear in `omissions` with a non-empty reason. A request omitting a protected fragment SHALL report `requiresApproval: true` and SHALL NOT be applicable until its approval has `decision: approved`, non-empty verbatim `human_words`, and `plan_digest` equal to the current computed digest. A request selecting all protected fragments SHALL require no composition approval.

#### Scenario: First validation requests judgement
- **WHEN** a valid request omits `security-review` with a reason but no approval
- **THEN** validation succeeds as a proposal, returns the plan digest, and reports `readyToApply: false`

#### Scenario: Matching approval
- **WHEN** the human approves the shown proposal and the request records their words with the returned digest
- **THEN** revalidation reports `readyToApply: true`

#### Scenario: Stale approval
- **WHEN** any digest-bearing plan content changes after approval
- **THEN** the old approval is rejected as stale and a new decision is required

### Requirement: Self-contained immutable plan materialization
Applying a ready composition SHALL create an immutable numbered plan directory containing a complete `schema.yaml`, `manifest.yaml`, and namespaced copies of all referenced instructions and templates. Copies SHALL be written only from the digest-bound in-memory resource bundle, and the manifest SHALL record and re-verify their hashes. The materialized schema SHALL be validated after copying. Runtime commands SHALL load only the materialized snapshot and SHALL NOT depend on later fragment or source-schema availability.

#### Scenario: Source changes after creation
- **WHEN** a source fragment, schema, template, or instruction changes after a composed change is created
- **THEN** status and instructions for that change continue using the original plan bytes

#### Scenario: Missing materialized resource
- **WHEN** staging fails to copy or validate any required resource
- **THEN** plan activation fails and no active metadata points at the incomplete directory

### Requirement: Atomic plan activation
Plan materialization SHALL use a staging directory, exclusive final revision creation, and atomic metadata replacement. A failure at any point before metadata replacement SHALL leave the previous workflow binding unchanged. Metadata plan paths SHALL be safe, relative, and contained within the change.

#### Scenario: Interrupted creation
- **WHEN** materialization fails before `.workflow.yaml` replacement
- **THEN** a legacy change remains bound to its schema and an existing composed change remains bound to its prior revision

#### Scenario: Tampered plan path
- **WHEN** metadata names an absolute or escaping plan path
- **THEN** loading the change fails with `config_invalid` without reading outside the change

### Requirement: Legacy schema compatibility
Changes whose metadata contains only `schema` and `created` SHALL retain their current behavior. `loopspec new <change> [--schema <name>]` SHALL remain supported, and complete schemas SHALL remain listable, validatable, and usable alongside composition.

#### Scenario: Existing change after upgrade
- **WHEN** status, instructions, rollback, history, or archive is run on a pre-composition change
- **THEN** results match the behavior before this feature

#### Scenario: New legacy change
- **WHEN** `loopspec new example --schema secure-spec-driven` is run without composition options
- **THEN** it creates traditional metadata and no plan directory

### Requirement: Composition-aware change creation
`loopspec new` SHALL accept `--composition <relative-request>` as mutually exclusive with `--schema` and `--profile`. It SHALL fully resolve and validate the request before creating the change directory, reject a proposal that is not ready to apply, and return plan revision, digest, selected fragments, omissions, and the existing first-step guidance on success.

#### Scenario: Composed change creation
- **WHEN** `new --composition` receives a ready request
- **THEN** revision 1 is materialized and status reports the first ready node of that effective graph

#### Scenario: Unapproved omission
- **WHEN** `new --composition` receives a valid proposal still requiring approval
- **THEN** it fails with `composition_approval_required` and writes no change directory

### Requirement: Progress remains filesystem-derived
The active plan SHALL define structure only. Node completion, gate verdicts, rollback counts, task progress, readiness, and completion SHALL continue to be computed from artifact, verdict, checkbox, and attempts files on every call.

#### Scenario: Artifact removed manually
- **WHEN** an artifact belonging to a completed composed node is removed
- **THEN** the next status recomputes that node as not done without editing plan metadata
