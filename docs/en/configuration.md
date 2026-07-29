# Configuration

> Scope: every field of `config.yaml`, the rules each one is validated against, how LoopSpec decides which schema a change uses, and four worked examples.
> Audience: humans setting up a project, and LLM agents that need to read or write a valid `config.yaml`.
> Language: **English** · [中文](../zh/configuration.md)

`config.yaml` sits at the root of the [workflow home](overview.md#glossary) and configures the project as a whole. `loopspec init` writes a two-line starter version:

<!-- loopspec:example=config -->
```yaml
artifacts_dir: changes
schema: secure-spec-driven
```

Everything else is optional. Unknown fields are rejected rather than ignored, so a typo such as `schemata:` fails with `config_invalid` instead of being silently dropped.

## Top-level fields

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| `artifacts_dir` | string | no | `changes` | Directory under the workflow home holding change directories. Must be a safe relative path: not absolute, no `..` component. |
| `schema` | string | no | none | Default schema name for new changes, and the fallback for existing changes with no `.workflow.yaml`. Must be kebab-case. When `schemas` is also set, this value must appear in `schemas[*].name`. |
| `schemas` | array of object | no | empty | Candidate schemas a change may be created with. See [`schemas[]` entries](#schemas-entries). Names must be unique. |
| `schema_selection` | object | no | none | How an agent should choose between multiple candidates. See [`schema_selection`](#schema_selection). |
| `context` | string | no | none | Project-wide context, returned verbatim as the `context` field of every `loopspec instructions` response. |
| `rules` | object | no | empty | Per-node extra rules: node id to a list of strings, returned as the `rules` field of that node's `loopspec instructions` response. |

At least one of `schema` or `schemas` must be present. A config with neither fails with `config_invalid` and the message `config.yaml must define schema or schemas`.

### `schemas[]` entries

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| `name` | string | yes | none | Schema directory name under `<home>/schemas/`, kebab-case. The directory must contain a loadable `schema.yaml`, checked when the config loads. |
| `path` | string | no | none | Subdirectory of the change directory to nest this schema's artifacts in. Must be a safe relative path. When unset, artifacts live directly in the change directory. |
| `description` | string | no | none | Human-readable summary, echoed in the `schema_selection_required` error payload. |
| `when` | string | no | none | When to pick this schema, echoed in the `schema_selection_required` error payload. |

### `schema_selection`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| `instruction` | string | yes | none | Instruction handed to an agent when a schema must be chosen. Returned as `selectionInstruction` in the `schema_selection_required` error payload. Must be non-empty. |

## Validation rules

Enforced when any command loads the config; each failure exits 1 with `config_invalid`.

| Rule | Message you will see |
| --- | --- |
| The file must exist. | `config.yaml not found in <home>` |
| No unknown top-level or nested fields. | Pydantic validation error naming the extra field. |
| `schema` or `schemas` must be present. | `config.yaml must define schema or schemas` |
| `schemas[*].name` must be unique. | `schemas[*].name must be unique` |
| `schema`, when combined with `schemas`, must be one of the candidates. | `schema must be included in schemas[*].name when both are configured` |
| `schema` and `schemas[*].name` must be kebab-case. | Pydantic pattern error. |
| `artifacts_dir` must be a safe relative path. | `artifacts_dir must be a safe relative path: <value>` |
| `schemas[*].path` must be a safe relative path. | `schemas[*].path must be a safe relative path: <value>` |
| Every candidate schema must be loadable. | `Candidate schema '<name>' cannot be loaded: <dir> not found` |

A `rules` key naming a node that the schema does not define is **not** an error. It surfaces as a `warnings` entry (`rules reference unknown node '<key>'`) in the `loopspec instructions` response, so a renamed node does not break the workflow.

## How the schema is resolved

There are two different resolution paths, and mixing them up is the most common configuration mistake. The difference is that a change records its schema in `.workflow.yaml` at creation time, so after creation the project default no longer decides anything.

| Situation | Order of precedence |
| --- | --- |
| Creating a change (`loopspec new`) | 1. `--schema` — but if `schemas` is configured, the value must be one of the candidates, else `config_invalid`. 2. If `schemas` has more than one entry: fail with `schema_selection_required`. 3. If `schemas` has exactly one entry: that one. 4. `schema`. 5. Fail with `config_invalid`. |
| Operating on an existing change (`status`, `instructions`, `rollback`, `history`, `archive`, `bulk-archive`) | 1. The change's own `.workflow.yaml`. 2. `schema`. 3. Fail with `config_invalid`. |

Consequences worth knowing:

- Changing `schema` in `config.yaml` does not migrate existing changes. They keep the schema recorded in their `.workflow.yaml`.
- Listing several candidates makes `--schema` mandatory for `loopspec new`. That is deliberate: it forces an explicit choice rather than silently picking the first entry.
- `.workflow.yaml` has two fields, both written by `loopspec new`: `schema` (the resolved schema name) and `created` (a `YYYY-MM-DD` date). It is not meant to be hand-edited, but editing `schema` is the supported way to move an in-flight change onto a different workflow.

## Examples

### Minimal

One schema, default layout. This is what `loopspec init` produces.

<!-- loopspec:example=config -->
```yaml
artifacts_dir: changes
schema: secure-spec-driven
```

### Multiple candidate schemas

Two workflows to choose from, plus the instruction an agent should follow when choosing. Note the absence of `schema`: with several candidates and no default, `loopspec new` always demands `--schema`.

<!-- loopspec:example=config -->
```yaml
artifacts_dir: changes
schemas:
  - name: secure-spec-driven
    description: Full spec-driven flow with security, approval and implementation gates
    when: Default choice for anything that touches production behaviour
  - name: docs-only
    description: Lightweight flow for documentation-only changes
    when: Use when no runtime code changes are involved
schema_selection:
  instruction: Ask the human which flow fits before creating the change.
```

Creating a change then looks like this:

```bash
loopspec new update-readme --schema docs-only --json
```

### Project context and per-node rules

`context` is prepended to every node's instruction payload; `rules` adds node-specific constraints. Both are passed through verbatim, so they are the place to encode house style without editing the schema itself.

<!-- loopspec:example=config -->
```yaml
artifacts_dir: changes
schema: secure-spec-driven
context: |
  This is a Python 3.11 project managed with uv. Tests run via `make test`,
  linting via `make lint`. Public APIs live in src/acme/api/.
rules:
  proposal:
    - Reference the tracking issue id in the first paragraph.
  design:
    - Call out every new third-party dependency explicitly.
    - Note any change to the public API surface.
  tasks:
    - Every task must be completable in one sitting.
```

### Custom layout

`artifacts_dir` renames the directory holding changes; `schemas[*].path` nests each change's artifacts in a subdirectory, which keeps `state.md` and `.workflow.yaml` visually separate from the documents themselves.

<!-- loopspec:example=config -->
```yaml
artifacts_dir: work-items
schema: secure-spec-driven
schemas:
  - name: secure-spec-driven
    path: artifacts
```

With that config, a change named `add-payment` lays out as:

```text
loopspec/
  work-items/
    add-payment/
      .workflow.yaml
      state.md
      artifacts/
        proposal.md
        design.md
        specs/<capability>/spec.md
        tasks.md
        security/pass.md
```

## Next

- [Schema reference](schema-reference.md) — the format of the `schema.yaml` files that `schema` and `schemas[*].name` point at.
- [CLI reference](cli-reference.md) — the commands that read this file.
