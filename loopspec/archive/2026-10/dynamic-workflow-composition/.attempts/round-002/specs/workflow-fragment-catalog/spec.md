## ADDED Requirements

### Requirement: Declarative fragment catalog
The system SHALL discover workflow fragments from `<home>/fragments/<name>/fragment.yaml`. Every fragment SHALL declare a kebab-case `name` matching its directory, a positive `version`, a non-empty `description`, an optional `when`, a `protected` boolean defaulting to false, and a non-empty list of `{schema, id}` node references. Unknown fields SHALL be rejected.

#### Scenario: Valid fragment is listed
- **WHEN** a valid fragment manifest references existing nodes in a valid schema
- **THEN** fragment listing returns its name, version, description, selection guidance, protection state, source node references, and resolved node IDs

#### Scenario: Manifest identity mismatch
- **WHEN** `fragments/security/fragment.yaml` declares `name: approval`
- **THEN** fragment validation fails with a structured error naming the identity mismatch

### Requirement: Fragment source resolution
The system SHALL resolve every fragment node through the same schema loader and schema-source resolver used by normal workflows. A referenced schema or node that cannot be resolved SHALL make the fragment invalid; no partial fragment SHALL be returned or composed.

#### Scenario: Unknown source node
- **WHEN** a fragment references node `review` in a schema that has no such node
- **THEN** validation rejects the fragment and identifies both the fragment and missing node

#### Scenario: Invalid source schema
- **WHEN** a fragment references a schema whose templates, paths, or graph fail existing validation
- **THEN** validation rejects the fragment using the underlying schema error without materializing a plan

### Requirement: Fragment paths remain inside trusted roots
All fragment, schema, instruction, and template paths SHALL be normalized and verified to remain inside their declared workflow-home roots after symlink resolution. Fragment manifests SHALL be parsed only as data and SHALL NOT declare commands, hooks, executable modules, or remote URLs.

#### Scenario: Symlink escape
- **WHEN** a fragment or referenced resource resolves through a symlink outside the workflow home or configured schema source
- **THEN** validation rejects the path and does not read or copy the escaped target

#### Scenario: Executable field in manifest
- **WHEN** a fragment manifest includes an unrecognized command or hook field
- **THEN** strict model validation rejects the manifest

### Requirement: Strict-additive composition surface
Fragments SHALL contribute complete source nodes only. They SHALL NOT patch, replace, remove, or relax fields on another fragment's nodes. Selecting duplicate fragment names or producing duplicate node IDs SHALL be a composition error even when the duplicate definitions are byte-identical.

#### Scenario: Duplicate node identity
- **WHEN** two selected fragments both contribute node `design`
- **THEN** composition fails and attributes the collision to both fragments

#### Scenario: No override semantics
- **WHEN** a fragment attempts to change only the gate policy of a node supplied by another fragment
- **THEN** the manifest is rejected instead of applying last-writer-wins behavior

### Requirement: Built-in secure workflow fragments
The packaged resources SHALL include fragments for `proposal`, `specs`, `design`, `tasks`, `security-review`, `approval`, and `implementation`, referencing the corresponding nodes of `secure-spec-driven`. `security-review` and `approval` SHALL be protected. `loopspec init` SHALL copy missing built-in fragments without overwriting local edits.

#### Scenario: Fresh initialization
- **WHEN** a new workflow home is initialized with built-in resources enabled
- **THEN** all seven fragments are available and the existing complete schema remains available

#### Scenario: Re-initialization preserves custom content
- **WHEN** a built-in fragment path already exists locally and `init` is run again
- **THEN** the local directory is not overwritten

### Requirement: Fragment catalog commands
`loopspec fragments list`, `loopspec fragments show <name>`, and `loopspec fragments validate <name>` SHALL support `--json`. Listing SHALL be deterministic by fragment name; show SHALL expose the validated manifest and resolved nodes; validate SHALL report validity and the resolved build order for that fragment's subgraph.

#### Scenario: Machine-readable catalog discovery
- **WHEN** an agent runs `loopspec fragments list --json`
- **THEN** it receives a stable array containing every valid fragment and enough metadata to decide whether to select it

#### Scenario: Unknown fragment
- **WHEN** an agent requests `fragments show missing --json`
- **THEN** the command exits with a structured `fragment_not_found` error and a corrective suggestion
