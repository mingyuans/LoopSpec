# Schema reference

> Scope: every field of `schema.yaml`, the directory layout a schema needs, all load-time validation checks with the error code each one raises, and a complete minimal schema you can copy.
> Audience: humans authoring a workflow, and LLM agents asked to write or repair a `schema.yaml`.
> Language: **English** · [中文](../zh/schema-reference.md)

A schema describes one workflow: which documents a change must produce, in what order, and which
steps are [gates](overview.md#glossary) that can send the work back. Schemas live in
`<home>/schemas/<name>/` and are referenced from `config.yaml`.

## Directory layout

```text
<home>/schemas/<name>/
  schema.yaml        # the node graph -- required
  templates/         # starting skeletons, one per node output
  instructions/      # instruction text, when a node uses `instruction: {file: ...}`
```

`schema.yaml` is the only required file. `templates/` becomes required as soon as any plain node
exists, because every plain node must name a template. `instructions/` is only needed for nodes that
reference an instruction file rather than inlining the text.

Both directories are sandboxes: a `template` or `instruction.file` value that resolves outside its
directory is rejected, so `../../etc/passwd` is not a usable template name.

## Top-level fields

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| `name` | string | yes | none | Schema name, kebab-case. Conventionally equal to the directory name; `loopspec schemas show` reports this value, not the directory. |
| `version` | integer | yes | none | Schema version, must be greater than 0. Informational — LoopSpec does not migrate between versions. |
| `description` | string | no | none | Human-readable summary of the workflow. |
| `nodes` | array of object | yes | none | The workflow's nodes. Must contain at least one entry. |

## `nodes[]` fields

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| `id` | string | yes | none | Node id, kebab-case, unique within the schema. Used by `requires`, `on_fail.reset`, and every CLI command that names a node. |
| `description` | string | yes | none | One-line description of the node, returned by `loopspec instructions` and shown as the dependency description upstream. |
| `generates` | string or null | for plain nodes | none | Artifact path relative to the artifact root. May be a glob such as `specs/**/*.md`. Must be `null` or omitted for a gate. |
| `template` | string or null | for plain nodes | none | Template filename under `templates/`. Its contents are returned as the `template` field of `loopspec instructions`. Must be `null` or omitted for a gate. |
| `requires` | array of string | no | empty | Node ids that must be `done` before this node becomes `ready`. Every id must exist, and the resulting graph must be acyclic. |
| `instruction` | string or object | no | none | The instruction text. Either an inline string, or `{file: <name>}` naming a file under `instructions/`. A node with no `instruction` returns an empty string. |
| `gate` | object | no | none | Turns this node into a gate. See [`gate`](#gate). |
| `tracks` | string | no | none | Path of a checkbox-bearing artifact whose completion gates this node. See [`tracks`](#tracks). |

### `instruction`

Two equivalent forms. Inline suits one-liners:

```yaml
- id: changelog
  generates: CHANGELOG-entry.md
  description: One-line changelog entry
  template: changelog.md
  instruction: Write exactly one line, in the past tense, naming the user-visible effect.
```

A file reference suits anything longer, and keeps `schema.yaml` readable:

```yaml
- id: proposal
  generates: proposal.md
  description: Initial proposal document outlining the change
  template: proposal.md
  instruction:
    file: proposal.md
```

The `file` value is resolved under `instructions/` and read at load time, so a missing file fails
fast with `instruction_not_found` rather than at the moment an agent asks for that node.

### `generates` and globs

A plain node is `done` once `generates` matches something. A concrete path must exist as a file. A
glob (any value containing `*`, `?` or `[`) is matched with `Path.glob` against the artifact root;
one or more matches count as done, and `loopspec status` reports every match, sorted.

Glob matching deliberately excludes two things: anything under `.attempts/`, so an archived previous
attempt never makes a reset node look done, and the reserved change-level files `state.md` and
`.workflow.yaml`, even when a broad glob such as `**/*.md` would otherwise match them.

### `tracks`

A node declaring `tracks` is only `done` when the tracked file exists **and** every checkbox in it is
ticked. This is what makes an implementation node wait for the actual work rather than for a report
to be written.

```yaml
- id: apply
  description: Implementation of the approved plan
  requires: [approval]
  tracks: tasks.md
  instruction:
    file: apply.md
  gate:
    outputs:
      pass: apply/report.md
      fail: apply/blocked.md
    templates:
      pass: apply-report.md
      fail: apply-blocked.md
    on_fail:
      reset: [design]
      max_retries: 2
```

Checkbox parsing recognises `- [ ]`, `- [x]`, `- [X]` and the `*`-prefixed equivalents, at any
indentation. A file with zero checkboxes counts as *not* complete, so an empty task list cannot make
a tracked node pass. Parsing never raises: a missing or unreadable tracked file reads as zero tasks,
and surfaces as a `tracked file not found: <path>` warning from `loopspec instructions`.

Constraints, all checked at load time:

- `tracks` must be a safe relative path — not absolute, no `..`.
- `tracks` must be a concrete path, not a glob. Progress has to come from one definite file.
- Some node must declare that exact path in its `generates`.
- At least one such producing node must be an ancestor of the tracking node, so the file is
  guaranteed to exist by the time the tracking node runs.

### `gate`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| `outputs` | object | yes | none | The two verdict paths. See [`gate.outputs`](#gateoutputs). |
| `templates` | object | yes | none | The two verdict templates. See [`gate.templates`](#gatetemplates). |
| `on_fail` | object | yes | none | What to redo when the verdict is FAIL. See [`gate.on_fail`](#gateon_fail). |

Writing the PASS file means the gate passed; writing the FAIL file means it failed. Writing both is
`gate_output_conflict`, because the verdict would be ambiguous — delete whichever file does not
reflect reality.

### `gate.outputs`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| `pass` | string | yes | none | Artifact path written when the gate passes. Must be concrete (no glob) and different from `fail`. |
| `fail` | string | yes | none | Artifact path written when the gate fails. Must be concrete (no glob) and different from `pass`. |

### `gate.templates`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| `pass` | string | yes | none | Template filename under `templates/` for the PASS verdict. |
| `fail` | string | yes | none | Template filename under `templates/` for the FAIL verdict. |

Both are returned by `loopspec instructions` as `templates.pass` and `templates.fail`, so the agent
sees both shapes before deciding the verdict.

### `gate.on_fail`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| `reset` | array of string | yes | none | Nodes to redo on FAIL. Must contain at least one id, and every id must be an ancestor of this gate. |
| `max_retries` | integer | no | `3` | How many rollbacks this gate may consume. Must be 0 or greater. Once used up, the gate becomes `exhausted` instead of `failed`. |
| `on_exhausted` | string | no | `escalate` | What exhaustion means: `escalate` (hand off to a human) or `stop`. |

`reset` names the *starting points*. The actual reset set is the closure: those nodes, the gate
itself, and every transitive dependent. Declaring `reset: [design]` in a graph where `tasks` requires
`design` and `security` requires `tasks` resets `design`, `tasks` and `security` — you do not list the
downstream nodes yourself.

Choosing `reset` is the main design decision in a gate. Reset the node that owns the *kind* of
mistake the gate detects: a security review finds "how" problems, so it resets `design`; a human
approval often rejects "what" is being built, so it resets `specs` as well.

## Reserved paths

`state.md` and `.workflow.yaml` belong to the change, not to any node. Declaring either as a
`generates`, `gate.outputs.pass` or `gate.outputs.fail` fails with `schema_invalid`. They are also
excluded from glob matching, and a rollback never archives them — which is what makes `state.md` the
only durable memory across rounds.

## Load-time validation

Loading happens in two phases: structural validation with Pydantic (unknown fields are errors, not
warnings), then semantic checks. The first failure raises; nothing is loaded partially.

| Check | Error code |
| --- | --- |
| YAML parses, and every field matches its declared type, with no unknown fields. | `schema_invalid` |
| `name` is kebab-case, `version` is greater than 0, `nodes` is non-empty. | `schema_invalid` |
| Node ids are unique. | `schema_invalid` |
| Every `requires` entry names an existing node. | `schema_invalid` |
| The `requires` graph is acyclic. The message names the full cycle, for example `alpha → beta → alpha`. | `schema_invalid` |
| A plain node has a non-empty `generates` and a non-empty `template`. | `schema_invalid` |
| A gate's `generates` and `template` are `null` or strings, never other types. | `schema_invalid` |
| A gate's `pass` and `fail` outputs are concrete (non-glob) and distinct. | `schema_invalid` |
| Every `template` path stays inside `templates/` and is a safe relative path. | `schema_invalid` |
| Every referenced template file exists. | `template_not_found` |
| No output path is a reserved name (`state.md`, `.workflow.yaml`). | `schema_invalid` |
| Every `on_fail.reset` entry names an existing node. | `schema_invalid` |
| Every `on_fail.reset` entry is an ancestor of its gate. The message lists the valid choices. | `schema_invalid` |
| `tracks` is a safe relative path. | `schema_invalid` |
| `tracks` is not a glob. | `schema_invalid` |
| `tracks` names a path some node declares in `generates`. | `schema_invalid` |
| At least one node generating the tracked path is an ancestor of the tracking node. | `schema_invalid` |
| Every `instruction.file` path stays inside `instructions/` and is a safe relative path. | `schema_invalid` |
| Every referenced instruction file exists. | `instruction_not_found` |

Run `loopspec schemas validate <name> --json` to execute all of it. On success you get the topological
build order, which is also the order `loopspec status` reports nodes in.

## A complete minimal schema

Two nodes: one document, then one gate reviewing it. Enough to be genuinely usable, and small enough
to read in one go.

<!-- loopspec:example=schema-dir -->
```yaml
name: draft-and-review
version: 1
description: Write a short draft, then review it

nodes:
  - id: draft
    generates: draft.md
    description: The draft document under review
    template: draft.md
    requires: []
    instruction:
      file: draft.md

  - id: review
    generates: null
    description: Review gate over the draft
    template: null
    requires: [draft]
    instruction:
      file: review.md
    gate:
      outputs:
        pass: review/approved.md
        fail: review/rejected.md
      templates:
        pass: review-approved.md
        fail: review-rejected.md
      on_fail:
        reset: [draft]
        max_retries: 2
        on_exhausted: escalate
```

The files it expects on disk:

```text
loopspec/schemas/draft-and-review/
  schema.yaml
  templates/
    draft.md
    review-approved.md
    review-rejected.md
  instructions/
    draft.md
    review.md
```

Wire it up and check it:

```bash
loopspec schemas validate draft-and-review --json
loopspec new my-first-change --schema draft-and-review --json
loopspec status my-first-change --json
```

The resulting flow: `draft` starts `ready`; once `draft.md` exists it is `done` and `review` becomes
`ready`; writing `review/approved.md` completes the change, while writing `review/rejected.md` makes
`review` `failed` and `loopspec rollback` moves `draft.md` and the rejection into
`.attempts/round-001/` so the draft can be rewritten with the rejection's blocking issues in hand.
After two rejections the gate is `exhausted` and asks for a human.

## Next

- [Configuration](configuration.md) — how a schema gets referenced from `config.yaml`.
- [secure-spec-driven](workflows/secure-spec-driven.md) — a worked seven-node schema with three gates.
- [Agent protocol](agent-protocol.md) — how an agent consumes what a schema declares.
