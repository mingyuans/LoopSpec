# Configuration

> Scope: every field of `config.yaml` and of assurance rule files, and when each is checked.
> Audience: people setting up or maintaining a project.
> Language: **English** · [中文](../zh/configuration.md)

## config.yaml

`loopspec init` writes `<home>/config.yaml`. It holds where Changes live and the project's minimum workflow constraints. Unknown fields are rejected, so fields of LoopSpec 1.x (`schema`, `schemas`, `schema_selection`, `context`, `rules`) and `workflow.default_profile` fail with `config_invalid` and must be deleted.

<!-- loopspec:example=config -->
```yaml
artifacts_dir: changes
workflow:
  required_fragments: [qa-testing, change-assurance]
  assurance_rules: fragments/change-assurance/rules.yaml
  generated_dirs: [node_modules, .venv]
```

### Top-level fields

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| `artifacts_dir` | relative path | no | `changes` | Directory under the workflow home that holds Changes. |
| `workflow` | mapping | no | - | Project constraints, below. |

### workflow fields

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| `required_fragments` | list of Fragment names | no | `[]` | Every Plan must instantiate each of them somewhere in its flow. |
| `assurance_rules` | home path | no | - | Project assurance rules. When set, every Plan needs an assurance node, and these rules are merged with the node's own. |
| `generated_dirs` | list of names | no | `[]` | Tool-generated directories left out of the Git diff. Only `.venv`, `node_modules`, `.pytest_cache`, `.mypy_cache`, `.ruff_cache` and `__pycache__` are accepted; anything else fails with `unsafe_exclusion`. |

### When it is read

Constraints are checked when a Plan is created and again when it is approved or revised, against the file as it is at that moment. During execution the diff exclusions and assurance rules are also read live. Changing `config.yaml` therefore affects running Plans immediately, including relaxing a rule; treat it as reviewed project code.

## Assurance rules

An assurance rules file maps changed paths to the capabilities that must be proven by code Gates. The built-in `change-assurance` Fragment ships `rules.yaml` with example paths; adjust them to the real layout of your project before relying on it.

<!-- loopspec:example=assurance-rules -->
```yaml
version: 1
unknown_paths: fail
rules:
- id: backend
  paths: [src/backend/**, backend/**, tests/backend/**]
  requires: [backend-tests, security-review, pr-review]
  repair_fragment: backend-implementation
- id: frontend
  paths: [src/frontend/**, frontend/**, tests/frontend/**]
  requires: [frontend-tests, pr-review]
  repair_fragment: frontend-implementation
```

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| `version` | integer | no | `1` | Format version. |
| `unknown_paths` | `fail` | no | `fail` | A changed path matching no rule fails assurance. |
| `rules` | list of rules | yes | - | 1 to 256 rules. |

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| `id` | kebab-case string | yes | - | Rule name; the same id in two files must have the same content. |
| `paths` | list of globs | yes | - | Changed paths the rule covers. When several rules match, their requirements are combined. |
| `requires` | list of capabilities | yes | - | Capabilities a code Gate must provide with valid evidence for every matching path. |
| `repair_fragment` | Fragment name | yes | - | Suggested Fragment when no Gate of the Plan can provide a capability. |

Gate `evidence.paths` in your Fragments and the rule `paths` must describe the same directories. A path nobody reviews either appears as `unknown_paths` or as `missing_fragments`; never widen `generated_dirs` to hide business code.
