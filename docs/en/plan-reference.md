# Plan reference

> Scope: `plan.yaml`, the Change-level `.workflow.yaml` and rework records, field by field; revisions, replanning and what an interruption leaves behind.
> Audience: anyone reviewing a Plan, and agents that revise or replan.
> Language: **English** · [中文](../zh/plan-reference.md)

## One Plan, one file

Each Plan is a single `changes/<change>/plans/<NNN>/plan.yaml` with two parts: `meta` records human decisions, `spec` is the execution graph. Every write replaces the whole file atomically. On every load the CLI recomputes the SHA-256 digest of `spec` and requires it to equal `meta.digest`; a hand-edited `spec` fails with `plan_integrity`.

`spec.flow` is what the agent requested, at instance granularity, kept for review, revision and `profile save`. `spec.nodes` is the compiled leaf graph; **the CLI navigates only `nodes`**, including each Gate's `on_fail`. Artifact and report paths are relative to the Plan directory; `instruction`, `template` and `assurance` are workflow-home paths read live when a node runs. Baseline and repository are not in the spec: they belong to the Change.

## Complete example

A Change `AFD1111` fixes an authorization bug. Plan 001 assumed a frontend problem and was archived with the human's consent; Plan 002 was drafted from the built-in `bugfix` Profile and approved. The `nodes` are the real compilation of that request.

<!-- loopspec:example=plan-file -->
```yaml
meta:
  plan: "002"
  status: approved
  revision: 1
  digest: 630c3781333a5cc0ba1635107e6875f55b95e34db6b0b69ba3cd0f4565b5576e
  approved_at: "2026-10-07T10:20:00+00:00"
  note: Plan 001 assumed a frontend bug; the cause is a missing ownership check in the backend
  created: "2026-10-07T10:05:00+00:00"
  archived_at: null
  archive_note: null
spec:
  based_on: bugfix
  flow:
  - id: requirements
    use: requirements
    requires: []
  - id: be
    use: backend-implementation
    requires: [requirements]
  - id: qa
    use: qa-testing
    requires: [be]
    on_fail:
      reset: [be]
      max_retries: 3
  - id: assurance
    use: change-assurance
    requires: [qa]
  nodes:
  - id: requirements/proposal
    fragment: requirements
    requires: []
    generates: artifacts/requirements/proposal.md
    instruction: fragments/requirements/proposal.instruction.md
    template: fragments/requirements/proposal.template.md
  - id: be/code/implement
    fragment: be/code
    requires: [requirements/proposal]
    generates: artifacts/be/code/implementation.md
    instruction: fragments/backend-code/implement.instruction.md
    template: fragments/backend-code/implement.template.md
  - id: be/tests/check
    fragment: be/tests
    requires: [be/code/implement]
    instruction: fragments/backend-tests/check.instruction.md
    gate:
      outputs: {pass: artifacts/be/tests/check/pass.md, fail: artifacts/be/tests/check/fail.md}
      templates: {pass: fragments/backend-tests/check.pass.md, fail: fragments/backend-tests/check.fail.md}
      evidence:
        provides: [backend-tests]
        paths: [src/backend/**, backend/**, tests/backend/**]
      on_fail:
        reset: [be/code/implement]
        max_retries: 3
  - id: be/security/check
    fragment: be/security
    requires: [be/tests/check]
    instruction: fragments/security-review/check.instruction.md
    gate:
      outputs: {pass: artifacts/be/security/check/pass.md, fail: artifacts/be/security/check/fail.md}
      templates: {pass: fragments/security-review/check.pass.md, fail: fragments/security-review/check.fail.md}
      evidence:
        provides: [security-review]
        paths: [src/backend/**, backend/**, tests/backend/**]
      on_fail:
        reset: [be/code/implement]
        max_retries: 3
  - id: be/review/check
    fragment: be/review
    requires: [be/security/check]
    instruction: fragments/backend-pr-review/check.instruction.md
    gate:
      outputs: {pass: artifacts/be/review/check/pass.md, fail: artifacts/be/review/check/fail.md}
      templates: {pass: fragments/backend-pr-review/check.pass.md, fail: fragments/backend-pr-review/check.fail.md}
      evidence:
        provides: [pr-review]
        paths: [src/backend/**, backend/**, tests/backend/**]
      on_fail:
        reset: [be/code/implement]
        max_retries: 3
  - id: qa/test
    fragment: qa
    requires: [be/review/check]
    instruction: fragments/qa-testing/test.instruction.md
    gate:
      outputs: {pass: artifacts/qa/test/pass.md, fail: artifacts/qa/test/fail.md}
      templates: {pass: fragments/qa-testing/test.pass.md, fail: fragments/qa-testing/test.fail.md}
      on_fail:
        reset: [be/code/implement, be/review/check, be/security/check, be/tests/check]
        max_retries: 3
  - id: assurance/check
    fragment: assurance
    requires: [qa/test]
    instruction: fragments/change-assurance/check.instruction.md
    gate:
      outputs: {pass: artifacts/assurance/check/pass.md, fail: artifacts/assurance/check/fail.md}
      assurance: fragments/change-assurance/rules.yaml
```

### Document fields

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| `meta` | PlanMeta | yes | - | Human decisions about this Plan. |
| `spec` | PlanSpec | yes | - | The execution graph; covered by `meta.digest`. |

### meta fields

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| `plan` | three-digit string | yes | - | The Plan number, equal to its directory name. |
| `status` | `draft`, `approved` or `archived` | yes | - | Human decision only; completion is derived, never stored. |
| `revision` | integer | yes | - | Confirmed revisions; `0` for a draft, `1` after the first approval. |
| `digest` | 64 hex characters | yes | - | Digest of `spec`; approval binds to it. |
| `approved_at` | timestamp or null | no | `null` | When the current revision was confirmed. |
| `note` | string or null | no | `null` | Why this Plan exists, from `plan create --note`. |
| `created` | timestamp | yes | - | Creation time. |
| `archived_at` | timestamp or null | no | `null` | Set only when archived. |
| `archive_note` | string or null | no | `null` | From `plan archive --note`. |

### spec fields

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| `based_on` | kebab-case string | no | - | Profile the request started from. |
| `flow` | list of flow entries | yes | - | The requested flow, see [Workflow composition](workflow-composition.md#plan-requests). |
| `nodes` | list of resolved nodes | yes | - | The compiled leaf graph the CLI executes. |

### Resolved node fields

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| `id` | instance path | yes | - | For example `be/tests/check`. |
| `fragment` | instance path | yes | - | The instance owning the node, for example `be/tests`. |
| `description` | string | no | - | Copied from the Fragment. |
| `requires` | list of node ids | no | `[]` | Leaf dependencies after expansion. |
| `generates` | path or glob | one of `generates`/`gate` | - | Artifact path under `artifacts/`. |
| `instruction` | home path | no | - | Instruction file, read live. |
| `template` | home path | no | - | Artifact template, read live. |
| `tracks` | path | no | - | Checklist artifact that must be fully ticked. |
| `gate` | resolved Gate | one of `generates`/`gate` | - | Gate definition including `on_fail`. |

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| `outputs` | GateOutputs | yes | - | PASS and FAIL report paths under `artifacts/`. |
| `templates` | GateTemplates | no | - | Report templates, read live. |
| `evidence` | CodeEvidence | no | - | Code Gate scope and capabilities. |
| `assurance` | home path | no | - | Rules file of the assurance node, read live. |
| `on_fail` | FailurePolicy | no | - | This Gate's single rework policy, `reset` already expanded to leaves. |

## Change-level state

`changes/<change>/.workflow.yaml` holds only what belongs to the Change rather than to one Plan. It stores no Plan pointers: the open Plan is the one whose `meta.status` is `draft` or `approved`, the active Plan is the `approved` one, and a new Plan gets the highest existing number plus one. Two open Plans fail with `history_integrity`. The Change status is derived and never stored.

<!-- loopspec:example=change-state -->
```yaml
format_version: 4
change_name: AFD1111
created: "2026-10-07T08:00:00+00:00"
baseline: 9f2c3e1d4b5a69788766554433221100ffeeddcc
repository: /path/to/project
```

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| `format_version` | integer | no | `4` | Only `4` is accepted; older Changes report `unsupported_format`. |
| `change_name` | string | yes | - | Equal to the directory name. |
| `created` | timestamp | yes | - | Creation time. |
| `baseline` | full commit hash or null | no | `null` | Fixed on the first `plan create`, never changed; every Plan diffs against it. |
| `repository` | path or null | no | `null` | Repository root fixed with the baseline; checked on every diff. |

## Rework records

`plan rollback` and a revision that re-runs nodes both archive workflow files of the affected nodes into `.attempts/<NNN>/files/` and describe it in `.attempts/<NNN>/record.yaml`. Numbers increase across both kinds. Only `rollback` records count against a Gate's `max_retries`; both kinds are shown to the re-run nodes as `priorAttempts`, marked as untrusted data.

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| `seq` | integer | yes | - | Record number, equal to its directory name. |
| `kind` | `rollback` or `revision` | yes | - | What caused the rework. |
| `created` | timestamp | yes | - | When the record was written. |
| `plan_digest` | 64 hex characters | yes | - | Digest of the spec at that moment. |
| `reset` | list of node ids | yes | - | Nodes that run again. |
| `files` | list of moves | yes | - | Files to archive, each with its content digest. |
| `gate` | node id | rollback only | - | The failed Gate. |
| `failure_digest` | 64 hex characters | rollback only | - | Digest of the archived FAIL report. |
| `target_digest` | 64 hex characters | revision only | - | Spec digest the revision leads to. |
| `revision` | integer | revision only | - | Revision number it leads to. |

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| `source` | Plan-relative path | yes | - | An artifact, Gate report or `.gates/<node>/` record of a reset node. |
| `destination` | Plan-relative path | yes | - | Always `.attempts/<seq>/files/<source>`. |
| `sha256` | 64 hex characters | yes | - | Content digest, checked when a re-run finishes the move. |

## Revisions

While a Plan still fits the task, adjust it in place. The agent writes a revision request with `base_revision`, runs `plan validate` to get the new digest, the added instances and the nodes that will run again, shows that to the human, and only after confirmation runs `plan approve -f <request> --digest <digest>`. Nothing is written before that.

- **Frozen nodes** are done, current, failed, or have rework history. They cannot be removed, renamed or have their execution definition changed (outputs, Gate, `on_fail`, resource paths).
- A frozen node may only **gain** `requires`. It and everything downstream are archived (`kind: revision`) and run again.
- Every Gate with an effective FAIL must be in that re-run set, so a revision cannot hide a failure.
- `base_revision` must equal the current `meta.revision`; otherwise `stale_revision`.
- Code Gate evidence is bound to the digest, so after a revision code Gates are reviewed again.

## Replanning

When the task itself changes, the agent shows the human the old Plan's progress (done, failed and exhausted Gates) and, only with explicit consent, runs `plan archive`. The Plan becomes `archived`, its directory is left untouched, and the Change returns to `unplanned`. The next `plan create` gets the next number and starts from an empty state on the same baseline: artifacts, evidence and retry counts are not inherited, and code changed under the old Plan must be reviewed again.

## Interrupted commands

There is no transaction file and no interrupted status. Every command has exactly one write that decides its outcome (the commit point). Writes before it are invisible to status and are overwritten or reused when the command runs again; work after it only moves files and never changes the derived status. An interrupted command therefore leaves the Change either as it was or as the command made it, and the agent continues from `change status` as usual.

| Command | Write order | Commit point |
| --- | --- | --- |
| `plan create` (new draft) | The baseline in `.workflow.yaml` the first time, the Plan's `state.md`, then `plan.yaml`. | `plan.yaml` |
| `plan approve` (draft) | `plan.yaml` approved. | The same write. |
| `plan archive` | `plan.yaml` archived. | The same write. |
| `plan rollback` | `record.yaml`, then each listed file, the FAIL report last. | `record.yaml` |
| `plan approve -f` (revision) | `record.yaml`, then `plan.yaml` replaced, then each listed file. | `plan.yaml` |

- A rollback record takes effect when written; a revision record takes effect once `plan.yaml` reaches its revision number. A revision record that never took effect is ignored, left out of history and `priorAttempts`, and replaced by the next record.
- Files an effective record still has to archive count as absent, so the reset nodes are ready to run again at once. `node instructions`, `gate`, `plan rollback`, `plan approve`, `plan archive` and `change archive` first finish those moves under the Change's write lock; `change status` only reads.
- Every move is checked against the digest in the record. When a source or an archived file does not match, or a record lists a path outside the reset nodes' workflow files, the command stops with `history_integrity` instead of guessing.
