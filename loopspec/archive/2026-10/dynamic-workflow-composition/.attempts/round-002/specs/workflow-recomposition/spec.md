## ADDED Requirements

### Requirement: Revision-checked recomposition
`loopspec recompose <change> --composition <relative-request>` SHALL accept a full replacement composition only for a plan-backed active change. The request's `base_revision` MUST equal the active revision. A mismatch SHALL reject the operation before materialization.

#### Scenario: Current revision
- **WHEN** a request names the active revision and satisfies all validation rules
- **THEN** recomposition may proceed to frozen-node comparison

#### Scenario: Concurrent stale request
- **WHEN** another recomposition has already advanced the active revision
- **THEN** the stale request fails with `plan_revision_stale` and the newer plan remains active

### Requirement: Executed and current work is frozen
Recomposition SHALL freeze every done, failed, or exhausted node; every node represented in attempts history; every node before the deterministic current cursor; and the first ready node itself. Each frozen node MUST remain present with the same semantic definition in the new plan.

#### Scenario: Remove completed node
- **WHEN** a replacement plan omits a node whose output currently makes it done
- **THEN** recomposition fails and names the frozen node

#### Scenario: Modify current cursor
- **WHEN** a replacement plan changes the first ready node's output, dependencies, instruction, template, tracking, or gate policy
- **THEN** recomposition fails before writing revision N+1

#### Scenario: Change future pending work
- **WHEN** selected fragments only add, remove, or modify nodes strictly after the cursor and the complete graph remains valid
- **THEN** the replacement plan is eligible for activation

### Requirement: Historical attempt evidence freezes ownership
If an attempts round records a node in `reset_closure`, or archives an artifact owned by a node, that node SHALL be frozen even when its current status is ready or blocked. Unreadable attempts metadata SHALL cause recomposition to fail rather than guessing.

#### Scenario: Previously failed future node
- **WHEN** a rollback has archived a node's output and the node is currently ready again
- **THEN** recomposition cannot remove or redefine that node

### Requirement: Recomposition creates immutable history
An accepted recomposition SHALL create revision N+1, retain all earlier plan directories, record the predecessor digest and change summary in the new manifest, and atomically update metadata. No existing plan directory SHALL be edited in place.

#### Scenario: Successful recomposition
- **WHEN** revision 1 is safely recomposed
- **THEN** revision 1 remains readable, revision 2 becomes active, and status uses revision 2

#### Scenario: Failed revision activation
- **WHEN** revision 2 staging or validation fails
- **THEN** revision 1 remains active and unchanged

### Requirement: Protected-gate policy applies to recomposition
Recomposition SHALL rerun protected-fragment policy over the replacement plan. Removing a not-yet-executed protected fragment SHALL require a reason and approval bound to the replacement digest, even if the previous revision had another approval.

#### Scenario: Remove pending security review
- **WHEN** revision 2 omits a pending protected security fragment
- **THEN** it cannot activate until a new matching approval is recorded

### Requirement: Project-authored fragments use identical validation
Users SHALL be able to add fragments below `<home>/fragments/`. Built-in and project-authored fragments SHALL use the same manifest schema, source resolution, composition validation, path restrictions, digest rules, and collision behavior.

#### Scenario: Valid custom fragment
- **WHEN** a project fragment references a valid custom schema node
- **THEN** it can be listed, selected, snapshotted, and recomposed like a built-in fragment

#### Scenario: Custom fragment collision
- **WHEN** a custom fragment conflicts with a built-in fragment's node or output ownership
- **THEN** composition rejects it without precedence based on origin

### Requirement: Reusable workflow profiles
`loopspec profiles save <name> --change <change>` SHALL save the active plan's fragment selection, inclusion reasons, omission reasons, description, and source digest to `<home>/profiles/<name>.yaml`. It SHALL reject unsafe names and conflicts unless an explicit overwrite option is provided. It SHALL never save approval words or make a prior approval reusable.

#### Scenario: Save reusable profile
- **WHEN** a valid composed change is saved as profile `focused-change`
- **THEN** the profile can be inspected and used as the base of another composition

#### Scenario: Approval is not copied
- **WHEN** the saved plan omitted a protected gate with approval
- **THEN** the profile contains the omission reason but not the approval, and a new change requires a new digest-bound decision

### Requirement: Profile-based creation
`loopspec new <change> --profile <name>` SHALL resolve the saved selection and reasons and compile against the current fragment catalog. If the profile retains all protected fragments, it may create directly. If it omits any protected fragment, creation SHALL require a workflow-home-relative approval overlay containing a matching digest-bound approval.

#### Scenario: Safe profile creates directly
- **WHEN** a profile selects every protected fragment
- **THEN** `new --profile` creates a new plan revision without asking for composition approval

#### Scenario: Profile sources changed
- **WHEN** a fragment or source schema changed after the profile was saved
- **THEN** current validation produces the current digest and graph; it does not silently reuse the profile's source digest

### Requirement: Plan history inspection
`loopspec plans show <change>` and `loopspec plans history <change>` SHALL report the active plan and immutable revisions without reading arbitrary paths. JSON output SHALL include revision, digest, predecessor digest, selected fragments, omissions, approval presence, and active state.

#### Scenario: Inspect recomposed change
- **WHEN** a change has two revisions
- **THEN** history reports both in ascending revision order and marks only revision 2 active
