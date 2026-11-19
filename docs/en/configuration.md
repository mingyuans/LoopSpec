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

An optional git repository (usually on GitHub) that maintains shared fragments and profiles. Configuring it puts the project in **registry mode**: the registry's fragments and profiles are no longer written into the project but kept in a per-user global store, and the project commits only `config.yaml` and `registry.lock.yaml`. The pinned version is changed with `loopspec registry update` and `loopspec registry apply` (see the [CLI reference](cli-reference.md)). Only one registry per project.

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

`loopspec registry apply` writes `<home>/registry.lock.yaml`; commit it together with `config.yaml`. It pins the registry commit the project uses and records the SHA-256 of every definition file in that commit. `loopspec init` never creates it. It is validated strictly as untrusted input; a malformed lock is `config_invalid`.

<!-- loopspec:example=registry-lock -->
```yaml
version: 2
registry:
  url: git@github.com:acme/loopspec-workflows.git
  version: latest
  path: workflows
commit: 3f2a9c1e5b7d4f60a8e2c3b1d9f7a6e5c4b3a2f1
tag: v1.4.0
files:
  fragments/qa-testing/fragment.yaml: 9c1e5b7d4f60a8e2c3b1d9f7a6e5c4b3a2f1e0d9c8b7a6f5e4d3c2b1a0f9e8d7
  profiles/bugfix.yaml: 51ab7d4f60a8e2c3b1d9f7a6e5c4b3a2f1e0d9c8b7a6f5e4d3c2b1a0f9e8d7c6
```

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| `version` | integer | no | `2` | Format version. The old format `1` (from when definitions were written into the project) is still read; the next `registry apply` rewrites it as `2`. |
| `registry` | registry mapping | yes | - | The registry this lock belongs to. When `url` or `path` differs from `config.yaml`, or `config.yaml` pins a tag and the lock's `tag` differs, reading definitions fails with `registry_lock_mismatch`; after changing `version`, run `registry update` and `registry apply` first. |
| `commit` | commit id | yes | - | The registry commit the project uses. |
| `tag` | tag or null | no | - | The release tag of that commit. |
| `files` | mapping | no | `{}` | Every definition file of that commit to the SHA-256 of its content. The set of definitions is derived from it, and the global snapshot is verified against it file by file. |

### Global store

Registry definitions are kept per source and commit under `$LOOPSPEC_REGISTRY_STORE` (default `~/.loopspec/registry`): `<store>/<source-id>/<commit>/`, where `source-id` looks like `<repository>[-<path>]-<hash8>`: the readable prefix is the last segment of `url` (without `.git`) plus `path`, lower-cased and reduced to `a-z0-9-` (at most 48 characters); `hash8` is the first 8 hex digits of the SHA-256 of `url` and `path`, so the SSH and HTTPS spellings of one repository are two sources. For example, `url: git@github.com:AfterShip/docs-coke-context.git` with `path: channels-loopspec` is stored under `~/.loopspec/registry/docs-coke-context-channels-loopspec-2d42f67b/<commit>/`. A snapshot is written to a temporary directory and published atomically, never changes afterwards, and is shared by every project and worktree on the machine. The directories must belong to the current user, must have no symlink anywhere in their path, and must not be group- or world-writable, otherwise `unsafe_path`; new directories are created `0700`.

- **Automatic fetch.** When a command reads definitions (`fragment list`, `plan create`, `node instructions`, assurance rules, ...) and the store has no snapshot of the locked commit yet, the CLI fetches that commit from the registry, verifies it completely against the lock, publishes it, and continues. When the lock names a `tag`, the CLI first checks that the tag still points at the locked commit in the registry, otherwise `registry_lock_mismatch`, so a forged lock cannot hide another commit behind a released tag. Note that this means a definition-reading command in an untrusted project may open a git connection to that project's `registry.url` and authenticate with your SSH agent or credential helper; check `config.yaml` and `registry.lock.yaml` of an unfamiliar project first. A fresh clone or worktree therefore needs no extra step; only the first fetch needs the network and git credentials. A failure is `registry_fetch_failed` and leaves no partial snapshot.
- **Integrity.** Every read is checked against the lock; a modified or incomplete snapshot is `registry_store_corrupt`. Delete the snapshot directory named in the message and retry to fetch it again. The CLI never replaces an existing snapshot by itself.
- **Local definitions.** The project may still keep its own definitions under `<home>/fragments/` and `<home>/profiles/`, as long as their names differ from the registry's. Both can be used in one Plan; `fragment list`/`profile list` tell them apart with `source`. A local file or directory with a registry definition's name makes every definition read fail with `registry_local_conflict`; delete those project copies.
- **Missing lock.** In registry mode, a missing `registry.lock.yaml` is `registry_not_synced`, and an old-format lock with skipped definitions (`held`) is `registry_lock_outdated`. Both are fixed with `registry update` and `registry apply`.

The cache directory `<home>/.cache/registry/` (sync plan and write lock) ignores itself through its own `.gitignore` and can be deleted at any time.

### Migrating from definitions inside the project

Copies of `fragments/` and `profiles/` that an earlier `registry apply` wrote into the project now carry registry names and fail with `registry_local_conflict`:

1. Delete the project definitions that share a name with the registry (keep only your own local definitions).
2. Run `loopspec registry update` and, after confirming, `loopspec registry apply --plan <planId>`; the lock is rewritten in the new format.
3. Commit the deletions and the new `registry.lock.yaml`.

### When it is read

Constraints are checked when a Plan is created and again when it is approved or revised, against the file as it is at that moment. During execution the diff exclusions and assurance rules are also read live. `<home>/.cache/` (the registry sync cache), memory topic files `<home>/memory/{topic}.md` (cross-Change memory) , the loopspec-generated skill and command files (only while the working tree holds a regular file with exactly this CLI's built-in content; deletions, edits and symlinks still count) and the current Change's `.workflow.yaml`, `state.md` and `plans/` are always left out of the diff without any configuration. Changing `config.yaml` therefore affects running Plans immediately, including relaxing a rule; treat it as reviewed project code.

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
