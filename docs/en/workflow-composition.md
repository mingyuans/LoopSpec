# Workflow composition

> Scope: writing Fragments, Profiles and Plan requests; how `on_fail` reaches Gates; code evidence and assurance.
> Audience: workflow authors and agents that draft Plans.
> Language: **English** · [中文](../zh/workflow-composition.md)

## Layers

| Layer | File | Role |
| --- | --- | --- |
| Node | inside `fragment.yaml` | One step: an artifact (`generates`) or a Gate (`gate`), or a `use` reference to another Fragment. |
| Fragment | `fragments/<name>/fragment.yaml` | A reusable, self-contained group of nodes with its own instructions and templates. |
| Profile | `profiles/<name>.yaml` | A reusable `flow` of Fragment instances; a template, never mandatory. |
| Plan | `changes/<change>/plans/<NNN>/plan.yaml` | The confirmed graph for one Change. See [Plan reference](plan-reference.md). |

Execution only ever follows a Plan's `spec.nodes`. Changing a Fragment or Profile definition never changes an approved Plan's graph; instructions, templates and assurance rules, however, are read live when a node runs.

## Fragments

A Fragment is a directory: `fragment.yaml` plus the resources it names (`<node>.instruction.md`, `<node>.template.md`, `<node>.pass.md`, `<node>.fail.md`, rule files). Resource paths are relative to that directory and cannot leave it. One `nodes` list mixes direct nodes and `use` references; there is no separate interface or include list.

<!-- loopspec:example=fragment -->
```yaml
version: 1
name: backend-implementation
description: Backend code, tests, security review and code review
nodes:
- id: code
  use: backend-code
- id: tests
  use: backend-tests
  requires: [code]
  on_fail: {reset: [code], max_retries: 3}
- id: security
  use: security-review
  requires: [tests]
  on_fail: {reset: [code], max_retries: 3}
- id: review
  use: backend-pr-review
  requires: [security]
  on_fail: {reset: [code], max_retries: 3}
```

### Fragment fields

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| `version` | integer | no | `1` | Format version; only `1` is accepted. |
| `name` | kebab-case string | yes | - | Must equal the directory name. |
| `description` | string | no | `""` | Shown by `fragment list`. |
| `nodes` | list of Node | yes | - | 1 to 256 nodes with unique `id`s. |

### Node fields

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| `id` | kebab-case string | yes | - | Unique within the Fragment. |
| `description` | string | no | `""` | Free text. |
| `use` | kebab-case string | no | - | Reference another Fragment; excludes every execution field below. |
| `requires` | list of node ids | no | `[]` | Sibling nodes that must be done first. |
| `generates` | relative path or glob | one of `generates`/`gate` | - | Artifact path, placed under `artifacts/<instance>/`. |
| `instruction` | relative path | no | - | Instruction file in this Fragment's directory. |
| `template` | relative path | no | - | Artifact template in this Fragment's directory. |
| `tracks` | relative path | no | - | A checklist artifact produced upstream in the same instance; the node is done only when every box is ticked. |
| `gate` | Gate | one of `generates`/`gate` | - | Makes the node a Gate. |
| `on_fail` | FailurePolicy | no | - | Rework policy; on a reference node it applies to every Gate inside. Not allowed on artifact nodes. |

### Gate fields

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| `outputs` | GateOutputs | yes | - | PASS and FAIL report paths; must differ. |
| `templates` | GateTemplates | no | - | PASS and FAIL report templates. |
| `evidence` | CodeEvidence | no | - | Makes it a code Gate whose verdict needs a recorded review round. |
| `assurance` | relative path | no | - | Makes it the assurance node; names the rules file. Excludes `evidence`. |

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| `pass` | relative path | yes | - | PASS report (in `outputs`) or template (in `templates`). |
| `fail` | relative path | yes | - | FAIL report or template. |

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| `provides` | list of kebab-case names | yes | - | Capabilities a PASS proves, for example `backend-tests`. |
| `paths` | list of globs | yes | - | Code paths this Gate reviews; the review round pins their current content. |

### FailurePolicy fields

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| `reset` | list of ids | yes | - | Upstream siblings (or flow instances) to redo. Expanded to leaf nodes at compile time. |
| `max_retries` | integer | no | `3` | Rollbacks allowed for each Gate it reaches, 0 to 100. |

## How on_fail reaches Gates

`on_fail` may be written on a direct Gate, on a reference node, or on a `flow` entry. Compilation pushes it down to every Gate inside that scope and expands `reset` into leaf node ids, so each Gate in `plan.yaml` carries at most one `gate.on_fail`. A Gate that would receive two policies fails compilation with `on_fail_conflict`; there is no implicit priority. When a Gate records an effective FAIL, `plan rollback` resets exactly that Gate's `reset` nodes, the Gate itself and everything downstream. Retries are counted per Gate.

## Profiles

<!-- loopspec:example=profile -->
```yaml
version: 1
name: bugfix
description: Bug fix with acceptance and assurance
flow:
- id: requirements
  use: requirements
- id: be
  use: backend-implementation
  requires: [requirements]
- id: qa
  use: qa-testing
  requires: [be]
  on_fail: {reset: [be], max_retries: 3}
- id: assurance
  use: change-assurance
  requires: [qa]
guidance:
- Adopt or adapt; the Plan still needs human confirmation.
```

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| `version` | integer | no | `1` | Format version. |
| `name` | kebab-case string | yes | - | Must equal the file name. |
| `description` | string | no | `""` | Shown by `profile list`. |
| `flow` | list of flow entries | yes | - | Fragment instances and their dependencies. |
| `guidance` | list of strings | no | `[]` | Advice for the planning agent; untrusted data. |

### Flow entry fields

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| `id` | kebab-case string | yes | - | Instance name; prefixes every node and artifact path. |
| `use` | kebab-case string | yes | - | Fragment to instantiate. |
| `requires` | list of instance ids | no | `[]` | Instances that must finish first. |
| `on_fail` | FailurePolicy | no | - | Applies to every Gate in the instance; `reset` names upstream instances. |

## Plan requests

An agent writes one request for the whole task and saves it under the Change's `plans/` directory, which the Git diff ignores. `plan validate` checks it without writing anything; `plan create` turns it into a draft Plan.

<!-- loopspec:example=plan -->
```yaml
based_on: bugfix
flow:
- id: requirements
  use: requirements
- id: be
  use: backend-implementation
  requires: [requirements]
- id: qa
  use: qa-testing
  requires: [be]
  on_fail: {reset: [be], max_retries: 3}
- id: assurance
  use: change-assurance
  requires: [qa]
```

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| `based_on` | kebab-case string | no | - | Profile the request started from; must exist. |
| `flow` | list of flow entries | yes | - | The complete flow for the task. |
| `base_revision` | integer | revisions only | - | For a revision of an approved Plan: its current `meta.revision`. |

A revision request is the same document with `base_revision`. It replaces the whole `flow`; see [Plan reference](plan-reference.md#revisions) for what may change.

<!-- loopspec:example=plan -->
```yaml
base_revision: 1
flow:
- id: requirements
  use: requirements
- id: fe
  use: frontend-implementation
  requires: [requirements]
- id: be
  use: backend-implementation
  requires: [requirements]
- id: qa
  use: qa-testing
  requires: [fe]
  on_fail: {reset: [fe], max_retries: 3}
- id: assurance
  use: change-assurance
  requires: [qa, be]
```

## Code evidence and assurance

A code Gate's verdict counts only through two commands. `gate begin` pins the content of the Gate's `evidence.paths` relative to the Change baseline and returns a one-time round id; the agent reviews or tests exactly that; `gate record` accepts a report holding only `verdict` and `summary`, rejects it if the pinned code changed, and writes the PASS or FAIL report together with evidence bound to the Plan digest. Editing the code afterwards makes the evidence stale and the Gate `ready` again.

The assurance node runs no review. `gate record` on it computes the full diff since the baseline, finds the capabilities the assurance rules require for every changed path, and checks that a code Gate of the active Plan with valid evidence provides them. It writes a system PASS, or a FAIL with `missing_evidence`, `stale_evidence`, `unknown_paths` and `missing_fragments` (with suggested Fragments). A handwritten `pass.md` never counts. Rules are described in [Configuration](configuration.md#assurance-rules).
