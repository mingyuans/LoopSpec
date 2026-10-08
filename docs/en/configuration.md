# Configuration

> Scope: every field of `config.yaml` and of assurance rule files, and when each is checked.
> Audience: people setting up or maintaining a project.
> Language: **English** · [中文](../zh/configuration.md)

## config.yaml

`loopspec init` writes `<home>/config.yaml`. It holds where Changes live and the project's minimum workflow constraints. Unknown fields are rejected, so fields of LoopSpec 1.x (`schema`, `schemas`, `schema_selection`, `context`, `rules`) and `workflow.default_profile` fail with `config_invalid` and must be deleted. `workflow.generated_dirs` was removed: move its names unchanged into `workflow.excluded_paths`, which means the same for them.

<!-- loopspec:example=config -->
```yaml
artifacts_dir: changes
workflow:
  required_fragments: [qa-testing, change-assurance]
  assurance_rules: fragments/change-assurance/rules.yaml
  excluded_paths: [node_modules, .venv, .DS_Store, docs/**]
```

### Top-level fields

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| `artifacts_dir` | relative path | no | `changes` | Directory under the workflow home that holds Changes. |
| `workflow` | mapping | no | - | Project constraints, below. |
| `registry` | mapping | no | - | Upstream git registry for fragments and profiles, below. |

### workflow fields

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| `required_fragments` | list of Fragment names | no | `[]` | Every Plan must instantiate each of them somewhere in its flow. |
| `assurance_rules` | home path | no | - | Project assurance rules. When set, every Plan needs an assurance node, and these rules are merged with the node's own. |
| `excluded_paths` | list of patterns | no | `[]` | Paths left out of the Git diff, up to 128. A pattern without `/` matches any single path component, file names included, such as `.DS_Store`, `__pycache__` or `*.log`. A pattern with `/` is matched with fnmatch against the whole repository-relative path, where `*` crosses directories, such as `docs/**` or `loopspec/config.yaml`. Matching paths need no review and raise no warning when ignored. Patterns must be safe relative paths: not empty, not starting with `/`, and without `.` or `..` components. |

### registry fields

An optional git repository (usually on GitHub) that maintains shared fragments and profiles. Fragments and profiles are still loaded only from `<home>/fragments/` and `<home>/profiles/`; the registry is their upstream, synced by `loopspec registry update` and `loopspec registry apply` (see the [CLI reference](cli-reference.md)). Only one registry per project, synced in full.

<!-- loopspec:example=config -->
```yaml
artifacts_dir: changes
workflow: {}
registry:
  url: git@github.com:acme/loopspec-workflows.git
  version: latest
  path: workflows
```

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| `url` | git URL | yes | - | `https://host/...`, `ssh://[user@]host/...`, `user@host:path` or `file:///abs/path`. `http://`, `git://`, transport syntax such as `ext::` and credentials inside the URL are rejected; authentication uses the local git setup (SSH agent or credential helper). |
| `version` | `latest` or tag | no | `latest` | `latest` follows the highest release tag (`v1.2.3`, pre-releases ignored), or the default branch when there is none. A fixed tag such as `v1.3.0` is not updated and, once synced, needs no network. |
| `path` | relative path | no | - | Directory inside the registry that holds `fragments/` and `profiles/`; the repository root when omitted. |

`latest` follows whatever higher tag the registry publishes; projects that need tighter supply-chain control pin a tag and protect the registry's branches and tags.

### registry.lock.yaml

`loopspec registry apply` writes `<home>/registry.lock.yaml`; commit it with `config.yaml`. It is the base of the three-way comparison and records which upstream version each definition came from. `loopspec init` never creates it and built-in resources carry no version. It is validated as untrusted input; a malformed lock fails with `config_invalid`.

<!-- loopspec:example=registry-lock -->
```yaml
version: 1
registry:
  url: git@github.com:acme/loopspec-workflows.git
  version: latest
  path: workflows
commit: 3f2a9c1e5b7d4f60a8e2c3b1d9f7a6e5c4b3a2f1
tag: v1.4.0
definitions:
  fragments/qa-testing: {tag: v1.3.0, commit: 3f2a9c1e5b7d4f60a8e2c3b1d9f7a6e5c4b3a2f1}
  profiles/bugfix: {tag: v1.4.0, commit: 3f2a9c1e5b7d4f60a8e2c3b1d9f7a6e5c4b3a2f1}
files:
  fragments/qa-testing/fragment.yaml: 9c1e5b7d4f60a8e2c3b1d9f7a6e5c4b3a2f1e0d9c8b7a6f5e4d3c2b1a0f9e8d7
  profiles/bugfix.yaml: 51ab7d4f60a8e2c3b1d9f7a6e5c4b3a2f1e0d9c8b7a6f5e4d3c2b1a0f9e8d7c6
```

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| `version` | integer | no | `1` | Format version. |
| `registry` | registry mapping | yes | - | The registry the lock was synced from. |
| `commit` | commit id | yes | - | Upstream commit of the last apply. |
| `tag` | tag or null | no | - | Release tag of that commit. |
| `definitions` | mapping | no | `{}` | `fragments/<name>` or `profiles/<name>` to the version that definition actually holds. A definition with a skipped file keeps its old version. |
| `held` | list of definitions | no | `[]` | Definitions with a skipped file. While any is held, `registry update` compares again even if the registry has not moved, so a skipped change is never forgotten. |
| `files` | mapping | no | `{}` | Each synced file to the SHA-256 of its upstream content, the base for telling local from upstream changes. |

A conflict resolved with `local` still counts as decided against that upstream version: the definition advances, and the file shows up as `local-modified` from then on. When `url` or `path` changes, the old lock is not used as a base: every difference is reported as a conflict and no deletion is planned.

Each `definitions` entry:

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| `tag` | tag or null | no | - | Release tag the definition was synced at. |
| `commit` | commit id | yes | - | Upstream commit the definition was synced at. |

The cache `<home>/.cache/registry/` (private bare repository, plans and staged files) ignores itself through its own `.gitignore` and can be deleted at any time.

### When it is read

Constraints are checked when a Plan is created and again when it is approved or revised, against the file as it is at that moment. During execution the diff exclusions and assurance rules are also read live. `<home>/.cache/` (the registry sync cache) and the current Change's `.workflow.yaml`, `state.md` and `plans/` are always left out of the diff without any configuration. Changing `config.yaml` therefore affects running Plans immediately, including relaxing a rule; treat it as reviewed project code.

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
| `unknown_paths` | `fail` or `warn` | no | `fail` | What happens to a changed path matching no rule. `fail` fails assurance; `warn` leaves the verdict alone: such paths are still listed in the diagnostics' `unknown_paths` and are reported as warnings (`warnings.unknownPaths`, at most 20, with `unknownTotal`) in the diagnostics and the system report's `summary`. When several rule files are merged, any file with `fail` makes it `fail`, so rules shipped with a Fragment cannot relax the project's. |
| `rules` | list of rules | yes | - | 1 to 256 rules. |

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| `id` | kebab-case string | yes | - | Rule name; the same id in two files must have the same content. |
| `paths` | list of globs | yes | - | Changed paths the rule covers. When several rules match, their requirements are combined. |
| `requires` | list of capabilities | yes | - | Capabilities a code Gate must provide with valid evidence for every matching path. |
| `repair_fragment` | Fragment name | yes | - | Suggested Fragment when no Gate of the Plan can provide a capability. |

Gate `evidence.paths` in your Fragments and the rule `paths` must describe the same directories. A path nobody reviews either appears as `unknown_paths` or as `missing_fragments`; `excluded_paths` accepts any value and a listed path no longer passes any Gate; never use it to hide business code, and review changes to it like project code.
